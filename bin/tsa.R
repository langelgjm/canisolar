# First, let's write Python to get all the data from EIA and store it in a SQL database # DONE
# Then we can pull it in here and generate forecasts which we also store in a different table # DONE
# Then we can query the DB from Python and join the historical and forecast tables


library(forecast)
library(RMySQL)

con <- dbConnect(MySQL(),
                 user = 'root',
                 password = '',
                 host = 'localhost',
                 dbname='eia')

sql <- "CREATE TABLE IF NOT EXISTS retail_residential_prices_predicted (
            id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY, 
            state CHAR(2),
            date DATE,
            price FLOAT
            )
            ENGINE=MyISAM"
dbGetQuery(conn=con, sql)

insert_future_prices <- function(row) {
  state = row[1]
  date = format(row[2])
  price = as.numeric(row[3])
  query <- sprintf("INSERT INTO retail_residential_prices_predicted (state, date, price) VALUES ('%s', '%s', %f)", state, format(date), price)
  dbGetQuery(con, query)
  #return(query)
}


prices <- dbGetQuery(conn=con, "SELECT * FROM retail_residential_prices ORDER BY state, date ASC")
sales <- dbGetQuery(conn=con, "SELECT * FROM retail_residential_sales ORDER BY state, date ASC")

by_state <- by(prices, prices[,"state"], function(x) x)
states <- names(by_state)

# For each state, do the following

forecast_prices <- function(my_state) {
  state <- prices[prices$state==my_state,]
  state_ts <- ts(state["price"], start=c(2001,1), frequency=12)
  #plot(state_ts)
  
  #components <- decompose(state_ts)
  #plot(components)
  
  # Automatically select a model
  # Bad practice, especially on some states, which give Unable to fit final model using maximum likelihood. AIC value approximated
  mod1 <- auto.arima(state_ts)
  # Give us 30 years of future values (obviously extending way past what is reasonable)
  forecasted_prices <- forecast(mod1, h=360)$mean
  #plot(forecast(mod1, h=360))
  # Convert to data.frame for SQL
  future_prices <- data.frame(state=rep(my_state, length(forecasted_prices)), date=as.Date(forecasted_prices), price=forecasted_prices, stringsAsFactors = FALSE)
  apply(future_prices, 1, insert_future_prices)  
  #return(future_prices)
}

lapply(states, forecast_prices)

forecast_sales <- function(my_state) {
  state <- sales[prices$state==my_state,]
  state_ts <- ts(state["sales"], start=c(2001,1), frequency=12)
  #plot(state_ts)
  
  components <- decompose(state_ts)
  plot(components)
  
  # Automatically select a model
  # Bad practice, especially on some states, which give Unable to fit final model using maximum likelihood. AIC value approximated
  #mod1 <- auto.arima(state_ts)
  # Give us 30 years of future values (obviously extending way past what is reasonable)
  #forecasted_prices <- forecast(mod1, h=360)$mean
  #plot(forecast(mod1, h=360))
  # Convert to data.frame for SQL
  #future_prices <- data.frame(state=rep(my_state, length(forecasted_prices)), date=as.Date(forecasted_prices), price=forecasted_prices, stringsAsFactors = FALSE)
  #apply(future_prices, 1, insert_future_prices)  
  #return(future_prices)
}