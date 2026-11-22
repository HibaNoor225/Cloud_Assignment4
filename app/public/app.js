$(function () {
  const money = new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  function isPositive(v) {
    const n = Number(v);
    return v !== '' && Number.isFinite(n) && n > 0;
  }

  function validateField($el, extra) {
    const ok = isPositive($el.val()) && (!extra || extra(Number($el.val())));
    $el.toggleClass('is-invalid', !ok);
    return ok;
  }

  function showError(msg) {
    $('#result-empty, #result-body').addClass('d-none');
    $('#result-error').text(msg).removeClass('d-none');
  }

  function showResult(r) {
    $('#result-empty, #result-error').addClass('d-none');
    $('#r-emi').text(money.format(r.emi));
    $('#r-total').text(money.format(r.totalPayment));
    $('#r-interest').text(money.format(r.totalInterest));
    $('#r-pod').text(r.servedBy);
    $('#r-ip').text(r.podIp);
    $('#result-body').removeClass('d-none');
  }

  function renderHistory(rows) {
    const $body = $('#history-body').empty();
    if (!rows.length) {
      $body.append('<tr><td colspan="6" class="text-muted">No calculations yet.</td></tr>');
      return;
    }
    rows.forEach(function (row) {
      $('<tr>')
        .append($('<td>').text(new Date(row.createdAt).toLocaleString()))
        .append($('<td class="text-end">').text(money.format(row.principal)))
        .append($('<td class="text-end">').text(row.rate))
        .append($('<td class="text-end">').text(row.months))
        .append($('<td class="text-end">').text(money.format(row.emi)))
        .append($('<td>').append($('<code>').text(row.servedBy)))
        .appendTo($body);
    });
  }

  function loadHistory() {
    $.getJSON('/api/history')
      .done(renderHistory)
      .fail(function () {
        $('#history-body').html('<tr><td colspan="6" class="text-danger">Could not load history (database unavailable).</td></tr>');
      });
  }

  $('#emi-form').on('submit', function (e) {
    e.preventDefault();
    const okP = validateField($('#principal'));
    const okR = validateField($('#rate'));
    const okN = validateField($('#months'), Number.isInteger);
    if (!(okP && okR && okN)) return;

    $('#submit-btn').prop('disabled', true);
    $('#spinner').removeClass('d-none');

    $.ajax({
      url: '/api/emi',
      method: 'POST',
      contentType: 'application/json',
      data: JSON.stringify({
        principal: Number($('#principal').val()),
        rate: Number($('#rate').val()),
        months: Number($('#months').val()),
      }),
    })
      .done(function (r) {
        showResult(r);
        loadHistory();
      })
      .fail(function (xhr) {
        const errs = xhr.responseJSON && xhr.responseJSON.errors;
        showError(errs ? errs.join(', ') : 'Request failed. Please try again.');
      })
      .always(function () {
        $('#submit-btn').prop('disabled', false);
        $('#spinner').addClass('d-none');
      });
  });

  $('#emi-form input').on('input', function () {
    $(this).removeClass('is-invalid');
  });

  $.getJSON('/api/version').done(function (v) {
    $('#app-version').text(v.version);
  });

  loadHistory();
});
