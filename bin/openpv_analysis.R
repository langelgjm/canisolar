library(RMySQL)
library(lme4)
library(rstan)
library(cvTools)

setwd("/Users/gjm/insight/canisolar/data/openpv_analysis")

con <- dbConnect(MySQL(),
                 user = 'root',
                 password = '',
                 host = 'localhost',
                 dbname='openpv')

# Get the OpenPV data
installs <- dbGetQuery(conn=con, "SELECT * FROM installs WHERE size > 0 AND cost > 0 ORDER BY state, date_installed ASC")

states <- unique(installs$state)

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

# A simple linear model is actually very good
mod_us <- lm(log(size) ~ log(cost), data=installs, na.action=na.omit)
#mod_us <- lm(log(installs$size) ~ log(installs$cost), na.action=na.omit)
summary(mod_us)

# Let's try the null multilevel model (terrible)
mod_ml_null <- lmer(log(cost) ~ 1 + (1 | state), data=installs)
summary(mod_ml_null)

# Now a multilevel model with individual and group data (better than linear)
mod_ml_1 <- lmer(log(cost) ~ log(size) + (1 | state), data=installs)
summary(mod_ml_1)

# Now a multilevel model with individual and group data, and where the effect of size varies between groups (best)
mod_ml_2 <- lmer(log(cost) ~ log(size) + (log(size) | state), data=installs)
summary(mod_ml_2)

# Let's crossvalidate these models to see which one predicts best
folds <- cvFolds(nrow(installs), K = 10, R = 1)

my_cv <- function(model, data, folds) {
  # create subset of data based on folds
  data_folded <- lapply(unique(folds$which), function(x) data[folds$subset[folds$which==x],])
  # apply an lm to each fold
  models_folded <- lapply(data_folded, function(x) update(model, data=x))
  #return(models_folded)
  # Get the mean residual sum of squares
  mean_rss <- Reduce("+", lapply(models_folded, function(x) sum(resid(x)^2))) / length(models_folded)
  return(mean_rss)
}

my_cv(mod_us, installs, folds)
my_cv(mod_ml_null, installs, folds)
# So both of these are better than a simple lm
my_cv(mod_ml_1, installs, folds)
my_cv(mod_ml_2, installs, folds)

# Save for later use
save(mod_ml_2, file="openpv_model.Robj")
load("openpv_model.Robj")
newdata = data.frame(state='MD', size=c(1234))
# What does it mean to not include random effects here?
exp(predict(mod_ml_2, newdata=data.frame(state='MD', size=8), re.form=NA))

# Now let's try this multilevel bayesian model stuff