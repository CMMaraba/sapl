/* Native crop editor for SAPL's x1,y1,x2,y2 crop fields. No vendor JS. */
(function () {
  "use strict";

  function parseBox(value) {
    var text = String(value || "");
    var full = text.charAt(0) === "-";
    if (full) text = text.slice(1);
    var parts = text.split(",").map(function (part) { return parseInt(part, 10); });
    if (parts.length !== 4 || parts.some(function (part) { return !Number.isFinite(part); })) {
      return { box: null, full: full };
    }
    if (parts[0] < 0 || parts[1] < 0 || parts[2] <= parts[0] || parts[3] <= parts[1]) {
      return { box: null, full: full };
    }
    return { box: parts, full: full };
  }

  function getFieldName(ratioField) {
    var field = ratioField.dataset.imageField || "";
    var marker = ratioField.dataset.myName || "";
    var name = ratioField.name || "";
    var index = marker ? name.lastIndexOf(marker) : -1;
    if (!field || index < 0) return "";
    return name.slice(0, index) + field + name.slice(index + marker.length);
  }

  function chooseFileInput(ratioField) {
    var form = ratioField.form || document;
    var targetName = getFieldName(ratioField);
    return Array.prototype.find.call(
      form.querySelectorAll('input[type="file"]'),
      function (input) { return input.name === targetName; }
    );
  }

  function clamp(value, min, max) {
    return Math.max(min, Math.min(value, max));
  }

  function initField(ratioField) {
    if (ratioField.dataset.saplCropReady === "1") return;
    var fileInput = chooseFileInput(ratioField);
    if (!fileInput) return;
    ratioField.dataset.saplCropReady = "1";

    var sourceUrl = fileInput.dataset.imageUrl || fileInput.dataset.thumbnailUrl || "";
    var sourceWidth = parseInt(fileInput.dataset.orgWidth || "0", 10);
    var sourceHeight = parseInt(fileInput.dataset.orgHeight || "0", 10);

    var container = document.createElement("div");
    container.className = "sapl-crop-ui";
    var stage = document.createElement("div");
    stage.className = "sapl-crop-stage";
    var image = document.createElement("img");
    image.className = "sapl-crop-image";
    image.alt = "Imagem para selecionar o recorte";
    image.draggable = false;
    var selection = document.createElement("div");
    selection.className = "sapl-crop-selection";
    stage.appendChild(image);
    stage.appendChild(selection);
    container.appendChild(stage);

    var help = document.createElement("p");
    help.className = "sapl-crop-help";
    help.textContent = "Arraste sobre a imagem para selecionar o recorte.";
    container.appendChild(help);

    var fullsizeAllowed = ratioField.dataset.allowFullsize === "true";
    var fullsizeInput = null;
    if (fullsizeAllowed) {
      var label = document.createElement("label");
      label.className = "sapl-crop-fullsize";
      fullsizeInput = document.createElement("input");
      fullsizeInput.type = "checkbox";
      label.appendChild(fullsizeInput);
      label.appendChild(document.createTextNode(" Usar imagem inteira"));
      container.appendChild(label);
    }

    ratioField.classList.add("sapl-crop-value");
    ratioField.hidden = true;
    ratioField.parentNode.insertBefore(container, ratioField.nextSibling);
    if (sourceUrl) image.src = sourceUrl;
    if (ratioField.dataset.hideImageField === "true") fileInput.hidden = true;

    var pointerStart = null;
    var currentBox = null;
    var fullsize = false;
    var objectUrl = null;

    function dimensions() {
      var rect = image.getBoundingClientRect();
      var width = sourceWidth || image.naturalWidth;
      var height = sourceHeight || image.naturalHeight;
      return { rect: rect, width: width, height: height };
    }

    function positionBox(box) {
      var dims = dimensions();
      if (!box || !dims.rect.width || !dims.rect.height || !dims.width || !dims.height) {
        selection.hidden = true;
        return;
      }
      var left = box[0] / dims.width * dims.rect.width;
      var top = box[1] / dims.height * dims.rect.height;
      var right = box[2] / dims.width * dims.rect.width;
      var bottom = box[3] / dims.height * dims.rect.height;
      selection.style.left = left + "px";
      selection.style.top = top + "px";
      selection.style.width = Math.max(0, right - left) + "px";
      selection.style.height = Math.max(0, bottom - top) + "px";
      selection.hidden = false;
    }

    function writeBox(box) {
      var dims = dimensions();
      var x1 = clamp(Math.round(box[0]), 0, Math.max(0, dims.width - 1));
      var y1 = clamp(Math.round(box[1]), 0, Math.max(0, dims.height - 1));
      var x2 = clamp(Math.round(box[2]), x1 + 1, dims.width);
      var y2 = clamp(Math.round(box[3]), y1 + 1, dims.height);
      currentBox = [x1, y1, x2, y2];
      var text = currentBox.join(",");
      ratioField.value = fullsize ? "-" + text : text;
      positionBox(currentBox);
    }

    function initialBox() {
      var parsed = parseBox(ratioField.value);
      fullsize = parsed.full;
      if (fullsizeInput) fullsizeInput.checked = fullsize;
      if (parsed.box) {
        currentBox = parsed.box;
      } else if (sourceWidth > 0 && sourceHeight > 0) {
        var ratio = parseFloat(ratioField.dataset.ratio || "0");
        if (ratio > 0 && sourceWidth / sourceHeight > ratio) {
          var cropWidth = sourceHeight * ratio;
          var x = Math.round((sourceWidth - cropWidth) / 2);
          currentBox = [x, 0, x + Math.round(cropWidth), sourceHeight];
        } else if (ratio > 0 && sourceWidth / sourceHeight < ratio) {
          var cropHeight = sourceWidth / ratio;
          var y = Math.round((sourceHeight - cropHeight) / 2);
          currentBox = [0, y, sourceWidth, y + Math.round(cropHeight)];
        } else {
          currentBox = [0, 0, sourceWidth, sourceHeight];
        }
        writeBox(currentBox);
      }
      positionBox(currentBox);
      if (fullsize) selection.classList.add("is-fullsize");
    }

    image.addEventListener("load", function () {
      if (!sourceWidth) sourceWidth = image.naturalWidth;
      if (!sourceHeight) sourceHeight = image.naturalHeight;
      stage.style.width = image.clientWidth + "px";
      stage.style.height = image.clientHeight + "px";
      initialBox();
    });

    if (fileInput) {
      fileInput.addEventListener("change", function () {
        var file = fileInput.files && fileInput.files[0];
        if (!file) return;
        if (objectUrl) URL.revokeObjectURL(objectUrl);
        objectUrl = URL.createObjectURL(file);
        sourceWidth = 0;
        sourceHeight = 0;
        ratioField.value = "";
        fullsize = false;
        if (fullsizeInput) fullsizeInput.checked = false;
        image.src = objectUrl;
      });
    }

    if (fullsizeInput) {
      fullsizeInput.addEventListener("change", function () {
        fullsize = fullsizeInput.checked;
        if (fullsize) {
          if (!currentBox) currentBox = [0, 0, sourceWidth, sourceHeight];
          selection.classList.add("is-fullsize");
        } else {
          selection.classList.remove("is-fullsize");
        }
        writeBox(currentBox || [0, 0, sourceWidth, sourceHeight]);
      });
    }

    function imagePoint(event) {
      var rect = image.getBoundingClientRect();
      return {
        x: clamp(event.clientX - rect.left, 0, rect.width),
        y: clamp(event.clientY - rect.top, 0, rect.height),
        rect: rect
      };
    }

    stage.addEventListener("pointerdown", function (event) {
      if (fullsize || !image.complete) return;
      event.preventDefault();
      var point = imagePoint(event);
      pointerStart = point;
      currentBox = null;
      selection.hidden = false;
      if (stage.setPointerCapture) stage.setPointerCapture(event.pointerId);
      positionBox([point.x / point.rect.width * sourceWidth,
        point.y / point.rect.height * sourceHeight,
        (point.x + 1) / point.rect.width * sourceWidth,
        (point.y + 1) / point.rect.height * sourceHeight]);
    });

    stage.addEventListener("pointermove", function (event) {
      if (!pointerStart || fullsize) return;
      var point = imagePoint(event);
      var dx = point.x - pointerStart.x;
      var dy = point.y - pointerStart.y;
      var width = Math.abs(dx);
      var height = Math.abs(dy);
      var ratio = parseFloat(ratioField.dataset.ratio || "0");
      if (ratio > 0 && width && height) {
        if (width / height > ratio) width = height * ratio;
        else height = width / ratio;
      }
      var x2 = clamp(pointerStart.x + (dx < 0 ? -width : width), 0, point.rect.width);
      var y2 = clamp(pointerStart.y + (dy < 0 ? -height : height), 0, point.rect.height);
      var x1 = Math.min(pointerStart.x, x2);
      var y1 = Math.min(pointerStart.y, y2);
      if (x2 <= x1 || y2 <= y1) return;
      var dims = dimensions();
      writeBox([
        x1 / dims.rect.width * dims.width,
        y1 / dims.rect.height * dims.height,
        x2 / dims.rect.width * dims.width,
        y2 / dims.rect.height * dims.height
      ]);
    });

    function stopSelection() { pointerStart = null; }
    stage.addEventListener("pointerup", stopSelection);
    stage.addEventListener("pointercancel", stopSelection);
    window.addEventListener("resize", function () { positionBox(currentBox); });
  }

  function initAll(root) {
    Array.prototype.forEach.call(
      (root || document).querySelectorAll("input.image-ratio"),
      initField
    );
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { initAll(document); });
  } else {
    initAll(document);
  }
  if (window.MutationObserver) {
    new MutationObserver(function (changes) {
      changes.forEach(function (change) {
        Array.prototype.forEach.call(change.addedNodes || [], function (node) {
          if (node.nodeType === 1) initAll(node);
        });
      });
    }).observe(document.documentElement, { childList: true, subtree: true });
  }
})();
