const test = require('node:test');
const assert = require('node:assert');
const { calculateEmi, validate } = require('../emi');

test('EMI for P=500000, rate=12%, n=24', () => {
  const r = calculateEmi(500000, 12, 24);
  assert.strictEqual(r.emi, 23536.74);
  assert.strictEqual(r.totalPayment, 564881.67);
  assert.strictEqual(r.totalInterest, 64881.67);
});

test('rejects zero, negative and non-numeric input', () => {
  assert.ok(validate({ principal: 0, rate: 12, months: 24 }).errors.length);
  assert.ok(validate({ principal: 100, rate: -1, months: 24 }).errors.length);
  assert.ok(validate({ principal: 'abc', rate: 12, months: 24 }).errors.length);
  assert.ok(validate({ principal: 100, rate: 12, months: 2.5 }).errors.length);
  assert.strictEqual(validate({ principal: '500000', rate: '12', months: '24' }).errors.length, 0);
});
