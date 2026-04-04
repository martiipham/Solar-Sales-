const expressRateLimit = require("express-rate-limit");

function rateLimit(limit) {
  return expressRateLimit({
    windowMs: 1 * 60 * 1000, // 1 minute
    max: limit, // Limit each IP to 'max' requests per 'windowMs'
    message:
      "Too many API calls from this IP, please try again after a minute"
  });
}

module.exports = rateLimit;
