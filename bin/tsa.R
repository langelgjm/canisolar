# This script creates forecasted estimates of electricity prices based on historical data from the EIA.
# It inserts these prices into an SQL database.

library(forecast)
library(RMySQL)

con <- dbConnect(MySQL(),
                 user = 'root',
                 password = '',
                 host = 'localhost',
                 dbname='eia')

# These table creation statements are duplicated in the Python class EIA_DB
sql <- "CREATE TABLE IF NOT EXISTS retail_residential_prices_predicted (
            id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY, 
            state CHAR(2),
            date DATE,
            price FLOAT
            )
            ENGINE=MyISAM"
dbGetQuery(conn=con, sql)

# These table creation statements are duplicated in the Python class EIA_DB
sql <- "CREATE TABLE IF NOT EXISTS retail_residential_prices_auto_arima (
            id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY, 
            state CHAR(2),
            date DATE,
            price FLOAT
            )
            ENGINE=MyISAM"
dbGetQuery(conn=con, sql)

sql <- "CREATE TABLE IF NOT EXISTS retail_residential_prices_lin_reg (
            id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY, 
            state CHAR(2),
            date DATE,
            price FLOAT
            )
            ENGINE=MyISAM"
dbGetQuery(conn=con, sql)

# Get the EIA data
prices <- dbGetQuery(conn=con, "SELECT * FROM retail_residential_prices ORDER BY state, date ASC")
#sales <- dbGetQuery(conn=con, "SELECT * FROM retail_residential_sales ORDER BY state, date ASC")

# Get a list of state names
states <- unique(prices$state)

insert_future_prices <- function(row, table) {
  state = row[1]
  date = format(row[2])
  price = as.numeric(row[3])
  query <- sprintf("INSERT INTO %s (state, date, price) VALUES ('%s', '%s', %f)", table, state, format(date), price)
  dbGetQuery(con, query)
  return(query)
}

forecast_prices_auto_arima <- function(my_state) {
  state <- prices[prices$state==my_state,]
  state_ts <- ts(state["price"], start=c(2001,1), frequency=12)
  
  # Auto ARIMA models should be checked by hand
  mod_auto <- auto.arima(state_ts, approximation=FALSE, ic="bic", parallel=TRUE, stepwise=FALSE)

  # Give us 60 years of future values (obviously extending way past what is reasonable)
  forecasted_prices <- forecast(mod_auto, h=720)$mean
  # Convert to data.frame for SQL
  future_prices <- data.frame(state=rep(my_state, length(forecasted_prices)), date=as.Date(forecasted_prices), price=forecasted_prices, stringsAsFactors = FALSE)
  apply(future_prices, 1, insert_future_prices, "retail_residential_prices_auto_arima")  
  return(my_state)
}

forecast_prices_lin_reg <- function(my_state, start_date) {
  # start_date should be a value of type Date
  state <- prices[prices$state==my_state,]
  x_vals = c(1:length(state$price))
  df = data.frame(price = state$price, time = x_vals)
  linear_mod <- lm(price ~ time, data=df)
  
  # Give us 60 years of future values (obviously extending way past what is reasonable)
  new_data = data.frame(time = c(172:891))
  forecasted_prices <- predict(linear_mod, new_data)
  
  # begin with this starting date
  new_dates = seq(start_date, by = "month", length.out = 720)

  future_prices <- data.frame(state=rep(my_state, length(forecasted_prices)), date=new_dates, price=forecasted_prices, stringsAsFactors = FALSE)
  apply(future_prices, 1, insert_future_prices, "retail_residential_prices_lin_reg")  
  return(my_state)
}

lapply(states, forecast_prices_lin_reg, as.Date("2015-04-01"))
lapply(states, forecast_prices_auto_arima)
