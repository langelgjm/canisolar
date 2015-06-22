library(RMySQL)
library(lme4)
library(rstan)
library(cvTools)
library(ggplot2)
library(parallel)

setwd("/Users/gjm/insight/canisolar/data/openpv_analysis")

con <- dbConnect(MySQL(),
                 user = 'root',
                 password = '',
                 host = 'localhost',
                 dbname='openpv')

# Get the OpenPV data
installs <- dbGetQuery(conn=con, "SELECT * FROM installs WHERE size > 0 AND cost > 0 AND date_installed >= '2000-01-01'  AND date_installed < '2015-06-01' ORDER BY state, date_installed ASC")
# Let's further subset this to get rid of outliers which are not going to be representative of residential instals:
# E.g., those with a cost larger than 1,000,000 and less than 1,000
installs <- installs[installs$cost > 1000 & installs$cost < 1000000,]
# Convert date strings to date objects
installs$date_installed <- as.Date(installs$date_installed)
# Create a factor for year of install:
installs$year_installed <- as.factor(as.POSIXlt(installs$date_installed)$year+1900)
# Create a factor for states:
installs$state <- as.factor(installs$state)
# Create a vector of state abbreviations
states <- unique(installs$state)

################################################################################
# Linear regression and multilevel models
################################################################################

# A simple linear model is actually very good
mod_simple <- lm(log(cost) ~ log(size), data=installs, na.action=na.omit)
summary(mod_simple)

# Fixed effects by year improves upon the above slightly
mod_fe_year <- lm(log(cost) ~ log(size) + year_installed, data=installs, na.action=na.omit)
summary(mod_fe_year)

# Let's fit a fixed effects model (dummy for each state, so that each state has its own intercept)
mod_fe_state <- lm(log(cost) ~ log(size) + state, data=installs, na.action=na.omit)
summary(mod_fe_state)

# Let's fit a fixed effects model (dummy for each state and each_year, so that each state has its own intercept)
mod_fe_state_year <- lm(log(cost) ~ log(size) + state + year_installed, data=installs, na.action=na.omit)
summary(mod_fe_state_year)

# Let's fit a fixed effects model (dummy for each state and each_year, so that each state has its own intercept) + interaction
#mod_fe_year_int <- lm(log(cost) ~ log(size) + state + year_installed + state:year_installed, data=installs, na.action=na.omit)
#summary(mod_fe_year_int)
# This took way too long

# Let's try the null multilevel model (terrible)
#mod_ml_null <- lmer(log(cost) ~ 1 + (1 | state), data=installs)
#summary(mod_ml_null)

# Model with varying intercept by year (this should be same as linear appoarch)
mod_ml_varint_year <- lmer(log(cost) ~ log(size) + (1 | year_installed), data=installs)
summary(mod_ml_varint_year)

# Now a multilevel model with individual and group data (better than linear)
mod_ml_varint_state <- lmer(log(cost) ~ log(size) + (1 | state), data=installs)
summary(mod_ml_varint_state)

# Now a multilevel model with individual and group data and year data (better than linear)
mod_ml_varint_state_year <- lmer(log(cost) ~ log(size) + (1 | state) + (1 | year_installed), data=installs)
summary(mod_ml_varint_state_year)

# Now a multilevel model with individual and group data, and where the effect of size varies between groups (best)
mod_ml_varslope_state <- lmer(log(cost) ~ log(size) + (log(size) | state), data=installs)
summary(mod_ml_varslope_state)

mod_ml_varslope_year <- lmer(log(cost) ~ log(size) + (log(size) | year_installed), data=installs)
summary(mod_ml_varslope_year)

# Now a multilevel model with individual and group data and year data, and where the effect of size varies between groups (best)
mod_ml_varslope_state_year <- lmer(log(cost) ~ log(size) + (log(size) | state) + (log(size) | year_installed), data=installs)
summary(mod_ml_varslope_state_year)

# Now a multilevel model with individual and group data and year data, and where the effect of size varies between groups (best)
mod_ml_varslope_nested_year_state <- lmer(log(cost) ~ log(size) + (log(size) | state/year_installed), data=installs)
summary(mod_ml_varslope_nested_year_state)
# Through cross validation, this is the best one
# Note that the assumption of normally distributed residuals does not hold

# Now a multilevel model with individual and group data and year data, and where the effect of size varies between groups (best)
mod_ml_varslope_nested_state_year <- lmer(log(cost) ~ log(size) + (log(size) | year_installed/state), data=installs)
summary(mod_ml_varslope_nested_state_year)

################################################################################
# Cross-validation
################################################################################

# Let's crossvalidate these models to see which one predicts best
my_cv <- function(model_name, data) {
  model = get(model_name)
  folds <- cvFolds(nrow(data), K = 10, R = 1)
  # create subset of data based on folds
  data_folded <- lapply(unique(folds$which), function(x) data[folds$subset[folds$which==x],])
  # apply an lm to each fold
  models_folded <- mclapply(data_folded, function(x) update(model, data=x), mc.cores=4)
  #return(models_folded)
  # Get the mean of the mean squared errors
  mean_mse <- Reduce("+", lapply(models_folded, function(x) mean(resid(x)^2))) / length(models_folded)
  return(mean_mse)
}

#models <- c("mod_simple", "mod_fe_state_year", "mod_ml_varslope_state_year", "mod_ml_varslope_nested_year_state")
models <- c("mod_simple", "mod_fe_year", "mod_fe_state", "mod_fe_state_year", "mod_ml_varint_year", "mod_ml_varint_state", "mod_ml_varint_state_year", "mod_ml_varslope_state", "mod_ml_varslope_year", "mod_ml_varslope_state_year", "mod_ml_varslope_nested_year_state", "mod_ml_varslope_nested_state_year")

cv_results <- sapply(models, my_cv, data=installs)
#cv_results2 <- sapply(models, my_cv, data=installs)
#cv_results3 <- sapply(models, my_cv, data=installs)
#cv_results4 <- sapply(models, my_cv, data=installs)
#cv_results5 <- sapply(models, my_cv, data=installs)

qqnorm(resid(mod_ml_varslope_nested_year_state))
qqline(resid(mod_ml_varslope_nested_year_state))    

################################################################################
# Random Forests
################################################################################

# Let's try a simple regression tree
library(randomForest)
tree_simple <- ctree(log(cost) ~ log(size), data=installs)
#forest_simple <- randomForest(log(installs$cost) ~ log(installs$size))
bound <- floor((nrow(installs)/4)*3)         #define % of training and test set
installs.orig <- installs[sample(nrow(installs)), ]           #sample rows 
installs.train <- installs.orig[1:bound, ]              #get training set
installs.test <- installs.orig[(bound+1):nrow(installs.orig), ]    #get test set

forest_simple <- randomForest(x=matrix(log(installs.train$size)), y=log(installs.train$cost), 
                              xtest=matrix(log(installs.train$size)), ytest=log(installs.train$cost))

#plot(fit, main="Conditional Inference Tree for Solar Installs")
tree_year <- ctree(log(cost) ~ log(size) + year_installed, data=installs)
tree_state <- ctree(log(cost) ~ log(size) + state, data=installs)
tree_year_state <- ctree(log(cost) ~ log(size) + year_installed + state, data=installs)

################################################################################
# Save the best model
################################################################################

# Save for later use
#save(mod_ml_varslope_nested_year_state, file="openpv_model.Robj")
save(mod_fe_state_year, file="openpv_model.Robj")
load("openpv_model.Robj")
newdata = data.frame(state='MD', size=c(1234))
# What does it mean to not include random effects here?
exp(predict(mod_ml_varslope_nested_year_state, newdata=data.frame(state='AK', size=5), re.form=NA))

################################################################################
# Other
################################################################################

# Let's graph the simple model by year
ggplot(installs, aes(x=log(size), y=log(cost))) + 
  geom_point(aes(color=year_installed), alpha=0.5) + 
  geom_abline(intercept=, slope=)
ggtitle("Cost($) vs Size (kW) of Solar Installations by Year")
ggsave("cost_vs_size_points.png")

mod_us_2014 <- lm(log(size) ~ log(cost), data=installs[installs$year_installed==2014,], na.action=na.omit)

png("CA_vs_OK_install_data.png", width=1600, height=1000, pointsize=24)
par(mfrow=c(1,2))
state = installs[installs$state=='CA',]
mod_ca <- lm(log(size) ~ log(cost), data=state, na.action=na.omit)
#bins <- hexbin(log(state$cost), log(state$size))
plot(log(state$size), log(state$cost), cex=0.1, main="California")
summary(mod_ca)

state = installs[installs$state=='OK',]
mod_ok <- lm(log(size) ~ log(cost), data=state, na.action=na.omit)
#bins <- hexbin(log(state$cost), log(state$size))
plot(log(state$size), log(state$cost), main="Oklahoma", pch=19)
summary(mod_ok)
dev.off()

openpv_graph_state <- function(state_name) {
  pdf(paste0(state_name, "_analysis.pdf"), width=8, height=5)
  par(mfrow=c(1,2))
  state_data = installs[installs$state==state_name,]
  plot(log(state_data$size), log(state_data$cost), xlab="Logged Size (kW)", ylab="Logged Cost ($)", main=state_name)
  hist(state_data$cost / (state_data$size * 1000), xlab="Cost per Watt ($)", main=state_name)
  dev.off()
}

lapply(states, openpv_graph_state)

plot(log(installs$size), log(installs$cost), xlab="Logged Size (kW)", ylab="Logged Cost ($)", main="US")
hist(installs$cost / (installs$size * 1000), xlab="Cost per Watt ($)", main="US")


r2.corr.mer <- function(m) {
  lmfit <-  lm(model.response(model.frame(m)) ~ fitted(m))
  summary(lmfit)$r.squared
}