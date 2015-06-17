library(forecast)
library(RMySQL)
# Could use the createTimeSlices function in caret, but I don't think it's very good
#library(caret) 
setwd("/Users/gjm/insight/canisolar/data/ts_plots")

con <- dbConnect(MySQL(),
                 user = 'root',
                 password = '',
                 host = 'localhost',
                 dbname='eia')

dbGetQuery(conn=con, sql)

prices <- dbGetQuery(conn=con, "SELECT * FROM retail_residential_prices ORDER BY state, date ASC")
#sales <- dbGetQuery(conn=con, "SELECT * FROM retail_residential_sales ORDER BY state, date ASC")

states <- unique(prices$state)

################################################################################
# Validation of time series models
################################################################################

validate_lm <- function(model_name, data, train_proportion=0.50) {
  # This expects a dataframe with numerically increasing integer indices for time as x, and price as y
  model = get(model_name)
  # Split data into train and test sets based on the the train_proportion
  # Note that you cannot randomly sample a time series to create these sets
  split_index = floor(nrow(data) * train_proportion)
  train = data[1:split_index,]
  test = data[(split_index + 1):nrow(data),]
  # using the call from the passed model, update it with the training set
  model <- update(model, data=train)
  # get the MSE on the training set
  train_mse <- mean(resid(model)^2)
  # predict values for the test set
  preds <- predict(model, newdata=test)
  #plot(data, type='l', xlim=c(0,nrow(data)), ylim=c(floor(min(data$y)),floor(max(data$y)) + 1))
  #abline(lm1, col='blue')
  #lines(test, col='red')
  test_mse <- mean((test$y - preds)^2)
  result = c(train_mse, test_mse)
  names(result) = c("train_mse", "test_mse")
  return(result)
}

validate_arima <- function(model_name, data, train_proportion=0.50) {
  model = get(model_name)
  # Split data into train and test sets based on the the train_proportion
  # Note that you cannot randomly sample a time series to create these sets
  split_index = floor(nrow(data) * train_proportion)
  train = data[1:split_index]
  train = ts(train, start=c(2001,1), frequency=12)
  test = data[(split_index + 1):nrow(data)]
  # split date is initial year plus number of training periods integer divided by 12, 
  # number of training periods modulo 12 plus 1
  split_date = c(2001 + length(train) %/% 12, length(train) %% 12 + 1)
  test = ts(test, start=split_date, frequency=12)
  #print(train)
  #print(test)
  # using the call from the passed model, update it with the training set
  model <- update(model, x=train)
  # get the MSE on the training set
  train_mse <- mean(resid(model)^2)
  # predict values for the test set
  fc <- forecast(model, h=length(test))
  #plot(fc)
  #lines(test, col='red')
  preds <- fc$mean
  test_mse <- mean((test - preds)^2)
  result = c(train_mse, test_mse)
  names(result) = c("train_mse", "test_mse")
  return(result)
}

validate_ets <- function(model_name, data, train_proportion=0.50) {
  model = get(model_name)
  # Split data into train and test sets based on the the train_proportion
  # Note that you cannot randomly sample a time series to create these sets
  split_index = floor(nrow(data) * train_proportion)
  train = data[1:split_index]
  train = ts(train, start=c(2001,1), frequency=12)
  test = data[(split_index + 1):nrow(data)]
  # split date is initial year plus number of training periods integer divided by 12, 
  # number of training periods modulo 12 plus 1
  split_date = c(2001 + length(train) %/% 12, length(train) %% 12 + 1)
  test = ts(test, start=split_date, frequency=12)
  # using the call from the passed model, update it with the training set
  model <- update(model, y=train)
  # get the MSE on the training set
  train_mse <- mean(resid(model)^2)
  # predict values for the test set
  fc <- forecast(model, h=length(test))
  #plot(fc)
  #lines(test, col='red')
  preds <- fc$mean
  test_mse <- mean((test - preds)^2)
  result = c(train_mse, test_mse)
  names(result) = c("train_mse", "test_mse")
  return(result)
}

validate_roll <- function(model_name, data, proportions=c(0.33, 0.5, 0.67)) {
  # Validates a model with different train/test splits (specified by proportions argument)
  # Print model name for indication of status
  print(paste("Validating", model_name))
  # Determine the type of validation function to use on the basis of the model call
  model_type = strsplit(toString(get(model_name)$call), ",")[[1]][1]
  if (model_type == "ets") {
    FUN = validate_ets
  } else if (model_type == "Arima" || model_type == "auto.arima") {
    FUN = validate_arima
  } else if (model_type == "lm") {
    FUN = validate_lm
    # validate_lm also needs a different data structure
    data = df = data.frame(x=c(1:length(data)), y=as.vector(data))
  }
  mses = sapply(proportions, FUN, model_name=model_name, data=data)
  #print(mses)
  result = rowMeans(mses)
  names(result) <- c("mean_train_mse", "mean_test_mse")
  return(result)
}

model_builder <- function(my_state, state_ts) {
  # Function to build a number of time series models, to be passed to validate_roll
  # Linear model (needs its own data)
  print(paste("State:", my_state))
  data = data.frame(x=c(1:length(state_ts)), y=as.vector(state_ts))
  lm1 <- lm(y ~ x, data=data)
  result <- list(lm1=lm1)
  # Auto ARIMA model
  # TODO: consider providing maximum parameter values to this
  # Actually, the Auto ARIMA and ETS models seems to cause more problems than they are worth
  #auto_arima <- auto.arima(x = state_ts)
  #result <- c(result, list(auto_arima=auto_arima))
  # Manual ARIMA models
  arima_100_100 <- Arima(state_ts, order=c(1,0,0), seasonal=c(1,0,0), include.drift=TRUE)
  arima_100_110 <- Arima(state_ts, order=c(1,0,0), seasonal=c(1,1,0), include.drift=TRUE)
  arima_100 <- Arima(state_ts, order=c(1,0,0), include.drift=TRUE)
  arima_110 <- Arima(state_ts, order=c(1,1,0), include.drift=TRUE)
  result <- c(result, list(arima_100_100=arima_100_100, arima_100_110=arima_100_100, arima_100=arima_100, arima_110=arima_110))
  # Auto Triple Exponential Smoothing model
  #auto_ets <- ets(y = state_ts, model="ZZZ")
  #result <- c(result, list(auto_ets=auto_ets))
  # Manual ETS models
  ets_zmm <- ets(state_ts, model="ZMM", damped=FALSE)
  ets_zaa <- ets(state_ts, model="ZAA", damped=FALSE)
  # Having some issues including these models without seasonal components
  #ets_zmn <- ets(state_ts, model="ZMN", damped=FALSE)
  #ets_zan <- ets(state_ts, model="ZAN", damped=FALSE)
  #result <- c(result, list(ets_zmm=ets_zmm, ets_zaa=ets_zaa, ets_zmn=ets_zmn, ets_zan=ets_zan))
  result <- c(result, list(ets_zmm=ets_zmm,  ets_zaa=ets_zaa))
  return(result)
}


model_selector <- function(my_state) {
  # Return the model name of the model with the lowest mean squared error, averaged over validation splits
  state <- prices[prices$state==my_state,]
  state_ts <- ts(state["price"], start=c(2001,1), frequency=12)
  models <- model_builder(my_state, state_ts)
  # Each model in the model list needs to be its own model in the global environment
  list2env(models, globalenv())
  mse_list = lapply(names(models), validate_roll, data=state_ts)
  # Name each element of the list with the name of its model
  names(mse_list) <- names(models)
  # Get the name of model with the minimum mean_test_mse
  element_name = names(which.min(sapply(mse_list, function(x) x[2])))
  model_name = strsplit(element_name, ".", fixed=TRUE)[[1]][1]
  print(paste("Selected Model:",model_name))
  return(model_name)
}

model_build <- function(my_state, model_name) {
  # Builds the selected model for the selected state
  state <- prices[prices$state==my_state,]
  state_ts <- ts(state["price"], start=c(2001,1), frequency=12)
  if (model_name == "lm1") {
    data = data.frame(x=c(1:length(state_ts)), y=as.vector(state_ts))
    model <- lm(y ~ x, data=data)
  } else if (model_name == "auto_arima") {
    model <- auto.arima(x = state_ts)
  } else if (model_name == "arima_100_100") {
    model <- Arima(state_ts, order=c(1,0,0), seasonal=c(1,0,0), include.drift=TRUE)
  } else if (model_name == "arima_100_110") {
    model <- Arima(state_ts, order=c(1,0,0), seasonal=c(1,1,0), include.drift=TRUE)
  } else if (model_name == "arima_100") {
    model <- Arima(state_ts, order=c(1,0,0), include.drift=TRUE)
  } else if (model_name == "arima_110") {
    model <- Arima(state_ts, order=c(1,1,0), include.drift=TRUE)
  } else if (model_name == "auto_ets") {
    model <- ets(y = state_ts, model="ZZZ")
  } else if (model_name == "ets_zmm") {
    model <- ets(state_ts, model="ZMM", damped=FALSE)
  } else if (model_name == "ets_zaa") {
    model <- ets(state_ts, model="ZAA", damped=FALSE)
  }
  return(model)
}

model_grapher <- function(my_state, model) {
  # Graphs predictions of the selected best model for each state
  print(paste("State:", my_state))  
  state <- prices[prices$state==my_state,]
  state_ts <- ts(state["price"], start=c(2001,1), frequency=12)  
  #print(paste("Graphing", model_name))
  # Determine the type of validation function to use on the basis of the model call
  model_type = strsplit(toString(model$call), ",")[[1]][1]
  pdf(paste0(my_state, ".pdf"))
  if (model_type == "ets" || model_type == "Arima" || model_type == "auto.arima") {
    plot(forecast(model, h=360))
  } else if (model_type == "lm") {
    data = data.frame(x=c(1:length(state_ts)), y=as.vector(state_ts))
    newdata = data.frame(x=c((nrow(data) + 1):(nrow(data) + 360)))
    preds <- predict(model, newdata=newdata)
    plot.default(x=newdata$x, y=as.vector(preds), type='l', col='blue', xlim=c(0,nrow(data)+360), ylim=c(floor(min(data$y)),floor(max(preds)) + 1))
    lines(data)
  }
  dev.off()
}

model_saver <- function(state_list, model_names) {
  # Builds and save the selected best model for each state into a named list
  model_list <- mapply(model_build, state_list, model_names, USE.NAMES=TRUE)
  # If you want to save each individual model in a separate file, you can use this
  #mapply(function(x,y) save(x, file=paste0(y,".Robj")), model_list, names(model_list))
  return(model_list)
}

mypredict <- function(model, x) {
  # x determines the number of periods into the future to return predictions for
  # I.e., periods after the final historical price month-year 
  model_type = strsplit(toString(model$call), ",")[[1]][1]
  if (model_type == "ets" || model_type == "Arima" || model_type == "auto.arima") {
    preds <- forecast(model, h=x)$mean
  } else if (model_type == "lm") {
    newdata = data.frame(x=(length(model$fitted.values) + 1):(length(model$fitted.values) + x))
    preds <- predict(model, newdata=newdata)
    # Convert vector to a TS to keep it consistent with the other models
    # Note that this start value is currently hardcoded
    preds <- ts(preds, start=c(2015,4), frequency=12)
  }
  return(preds)
}

################################################################################
# select the best of the validated models, build the best, graph them, 
# save them in a named list, then save the list to a file
# also save the prediction function to a separate file
################################################################################

best_model_names <- sapply(states, function(x) model_selector(x))
models <- mapply(model_build, names(best_model_names), best_model_names)
mapply(model_grapher, names(best_model_names), models)

ts_model_list <- model_saver(names(best_model_names), best_model_names)
save(ts_model_list, file="ts_model_list.Robj")
#load("ts_model_list.Robj")
save(mypredict, file="ts_mypredict.Robj")

# This is how to call the prediction function; note the double brackets
#mypredict(ts_model_list[['CO']], 200)

################################################################################
# Old stuff
################################################################################


eight_plot <- function(state_name) {
  pdf(paste0(state_name, "_8plot.pdf"), width=10, height=8)
  par(mfrow=c(4,2))
  state <- prices[prices$state==state_name,]
  state_ts <- ts(state["price"], start=c(2001,1), frequency=12)
  plot(state_ts, main="Run Sequence")
  # first difference to remove trend
  state_ts_fd <- diff(state_ts, lag=1, differences=1)
  plot(state_ts_fd, main="1st Diff")
  # now remove seasonality
  state_ts_fd_no_s <- diff(state_ts_fd, lag=12, differences=1)
  plot(state_ts_fd_no_s, main="1st Diff, 12 Per Lag")
  qqnorm(state_ts_fd_no_s)
  qqline(state_ts_fd_no_s)    
  # acf
  acf(state_ts_fd_no_s, lag.max=60)
  # pacf
  acf(state_ts_fd_no_s, lag.max=60, type="partial")
  mod_auto <- auto.arima(state_ts, approximation=FALSE, ic="bic", parallel=TRUE, stepwise=FALSE)
  plot(forecast(mod_auto, h=60))
  plot(forecast(mod_auto, h=360))
  dev.off()
  state_ts_fd_no_s
}

# 4-plot
four_plot <- function (x) {
  lag.plot(x, layout=c(2,2))
  par(mfg=c(1,2))  
  plot(x, main="Run Series Plot")
  hist(x)
  qqnorm(x)
  qqline(x)
}