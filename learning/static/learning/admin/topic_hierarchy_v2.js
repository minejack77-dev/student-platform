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

  function loadOptions($select, params, selectedValue, callback) {
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
      if (selectedValue && $select.find('option[value="' + selectedValue + '"]').length) {
        $select.val(String(selectedValue));
      }
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

    function syncWorkbookAndUnit(workbookValue, unitValue) {
      if (!$subject.val()) {
        resetSelect($workbook);
        resetSelect($unit);
        return;
      }

      loadOptions($workbook, { subject: $subject.val() }, workbookValue, function () {
        var activeWorkbookValue = $workbook.val();
        if (!activeWorkbookValue) {
          resetSelect($unit);
          return;
        }
        loadOptions($unit, { workbook: activeWorkbookValue }, unitValue);
      });
    }

    $subject.on("change", function () {
      syncWorkbookAndUnit($workbook.val(), $unit.val());
    });

    $workbook.on("change", function () {
      loadOptions($unit, { workbook: $workbook.val() }, $unit.val());
    });

    if ($subject.val()) {
      syncWorkbookAndUnit($workbook.val(), $unit.val());
    } else if (!hasRealOptions($workbook)) {
      resetSelect($workbook);
      resetSelect($unit);
    }
  });
})();
