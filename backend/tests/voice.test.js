const express = require('express');
const router = express.Router();
const { receiveCall } = require('../src/voice');

describe('Voice Handling', () => {
  it('should reject calls without valid Twilio SID', async done => {
    const req = { headers: {} };
    const res = {
      status: jest.fn().mockReturnThis(),
      send: jest.fn()
    };

    await receiveCall(req, res);
    expect(res.status).toHaveBeenCalledWith(403);
    expect(res.send).toHaveBeenCalledWith('Invalid Twilio SID');

    done();
  });

  it('should accept calls with valid Twilio SID', async done => {
    const req = { headers: { 'x-twilio-signature': 'some-signature' } };
    const res = {
      status: jest.fn().mockReturnThis(),
      send: jest.fn()
    };

    await receiveCall(req, res);
    expect(res.status).not.toHaveBeenCalled();
    expect(res.send).not.toHaveBeenCalled();

    done();
  });
});
