const express = require('express');
const router = express.Router();
const controller = require('./webhookController');

router.post('/', controller.handleWebhook);

module.exports = router;
