function round2(x) {
  return Math.round(x * 100) / 100;
}

function parsePositive(value) {
  if (value === undefined || value === null || value === '') return NaN;
  const n = Number(value);
  return Number.isFinite(n) && n > 0 ? n : NaN;
}

function validate(body) {
  const principal = parsePositive(body.principal);
  const rate = parsePositive(body.rate);
  const months = parsePositive(body.months);
  const errors = [];
  if (Number.isNaN(principal)) errors.push('principal must be a positive number');
  if (Number.isNaN(rate)) errors.push('rate must be a positive number');
  if (Number.isNaN(months)) errors.push('months must be a positive number');
  else if (!Number.isInteger(months)) errors.push('months must be a whole number');
  return { principal, rate, months, errors };
}

// EMI = P * r * (1 + r)^n / ((1 + r)^n - 1), r = annual rate / 12 / 100
function calculateEmi(principal, annualRate, months) {
  const r = annualRate / 12 / 100;
  const factor = Math.pow(1 + r, months);
  const emi = (principal * r * factor) / (factor - 1);
  const totalPayment = emi * months;
  return {
    emi: round2(emi),
    totalPayment: round2(totalPayment),
    totalInterest: round2(totalPayment - principal),
  };
}

module.exports = { calculateEmi, validate };
