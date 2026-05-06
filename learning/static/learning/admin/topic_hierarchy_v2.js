(function () {
  var $ = window.jQuery || (window.django && window.django.jQuery);

  if (!$) {
    return;
  }

  function resetSelect($select) {
    $select.empty();
    $select.append(new Option("---------", "", true, true));
    $select.val("");
  }

  function hasRealOptions($select) {
    return $select.find("option").filter(function () {
      return this.value;
    }).length > 0;
  }

  function loadOptions($select, params, callback) {
    var url = $select.data("options-url");
    resetSelect($select);
    if (!url) {
      if (callback) {
        callback();
      }
      return;
    }

    $.getJSON(url, params, function (payload) {
      (payload.results || []).forEach(function (item) {
        $select.append(new Option(item.text, item.id, false, false));
      });
      if (callback) {
        callback(payload.results || []);
      }
    });
  }

  $(function () {
    var $subject = $("#id_subject");
    var $workbook = $("#id_workbook");
    var $unit = $("#id_unit");

    if (!$subject.length || !$workbook.length || !$unit.length) {
      return;
    }

    $subject.on("change", function () {
      loadOptions($workbook, { subject: $subject.val() });
      resetSelect($unit);
    });

    $workbook.on("change", function () {
      loadOptions($unit, { workbook: $workbook.val() });
    });

    if ($subject.val() && !$workbook.val() && !hasRealOptions($workbook)) {
      loadOptions($workbook, { subject: $subject.val() });
    }

    if ($workbook.val() && !$unit.val() && !hasRealOptions($unit)) {
      loadOptions($unit, { workbook: $workbook.val() });
    }
  });
})();
