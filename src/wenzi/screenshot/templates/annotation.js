/**
 * annotation.js — Annotation canvas controller for WenZi screenshot tool.
 *
 * Communicates with Python via the `wz` bridge (injected by WKWebView):
 *   wz.send(event, data)  — fire event to Python
 *   wz.on(event, callback) — listen for events from Python
 *
 * Initialization: Python sends "init" event with {imageUrl, width, height}.
 * Export: Python sends "export" event; JS responds with "exported" + dataUrl.
 */

(function () {
  "use strict";

  // ── State ──

  var canvas = null;
  var bgImage = null; // background fabric.Image (not selectable)
  var hiddenCanvas = null; // for mosaic pixel reading
  var hiddenCtx = null;

  var currentTool = null; // null | "rect" | "ellipse" | "arrow" | "line" | "pen" | "mosaic" | "text" | "number"
  var currentColor = "#ff4d4f";
  var currentThickness = "medium";
  var numberCounter = 1;

  // Thickness values in pixels
  var THICKNESS = { thin: 2, medium: 4, thick: 6 };
  // Mosaic block sizes per thickness
  var MOSAIC_BLOCK = { thin: 8, medium: 12, thick: 18 };

  // Undo/Redo
  var stateStack = [];
  var stateIndex = -1;
  var MAX_STACK = 50;
  var savingState = false; // guard against recursive saves

  // Drag state for shape tools
  var isDrawing = false;
  var drawStart = null; // {x, y}
  var activeShape = null; // the shape being drawn

  // ── Initialization ──

  // Signal Python that handlers are registered
  wz.send("ready");

  wz.on("init", function (data) {
    var w = data.width;
    var h = data.height;
    var imageUrl = data.imageUrl;

    // Create Fabric canvas
    canvas = new fabric.Canvas("annotation-canvas", {
      width: w,
      height: h,
      selection: false,
      renderOnAddRemove: true,
    });

    // Load background image
    fabric.FabricImage.fromURL(imageUrl, { crossOrigin: "anonymous" }).then(
      function (img) {
        bgImage = img;
        img.set({
          left: 0,
          top: 0,
          scaleX: w / img.width,
          scaleY: h / img.height,
          selectable: false,
          evented: false,
          excludeFromExport: false,
        });
        canvas.backgroundImage = img;
        canvas.renderAll();

        // Create hidden canvas for mosaic pixel reading
        hiddenCanvas = document.createElement("canvas");
        hiddenCanvas.width = w;
        hiddenCanvas.height = h;
        hiddenCtx = hiddenCanvas.getContext("2d", {
          willReadFrequently: true,
        });
        // Draw background onto hidden canvas
        hiddenCtx.drawImage(img.getElement(), 0, 0, w, h);

        // Save initial state
        saveState();
        updateUndoRedoButtons();
      }
    );

    // Wire up canvas events
    setupCanvasEvents();
  });

  // ── Export ──

  wz.on("export", function () {
    if (!canvas) return;
    var dataUrl = canvas.toDataURL({ format: "png", multiplier: 1 });
    wz.send("exported", { dataUrl: dataUrl });
  });

  // ── Canvas Events ──

  function setupCanvasEvents() {
    canvas.on("mouse:down", onMouseDown);
    canvas.on("mouse:move", onMouseMove);
    canvas.on("mouse:up", onMouseUp);

    // Double-click on canvas = confirm
    canvas.on("mouse:dblclick", function () {
      // Only confirm if not currently editing text
      var activeObj = canvas.getActiveObject();
      if (activeObj && activeObj.isEditing) return;
      wz.send("confirm");
    });

    // Save state when objects are modified (moved, scaled, rotated)
    canvas.on("object:modified", function () {
      saveState();
    });

    // Save state after free drawing path is created
    canvas.on("path:created", function () {
      saveState();
    });
  }

  function onMouseDown(opt) {
    if (!currentTool) return;
    var pointer = canvas.getViewportPoint(opt.e);

    if (currentTool === "text") {
      placeText(pointer);
      return;
    }

    if (currentTool === "number") {
      placeNumber(pointer);
      return;
    }

    if (currentTool === "pen") {
      // PencilBrush handles its own drawing
      return;
    }

    // Shape tools: rect, ellipse, arrow, line, mosaic
    isDrawing = true;
    drawStart = { x: pointer.x, y: pointer.y };
    canvas.selection = false;

    if (currentTool === "rect") {
      activeShape = new fabric.Rect({
        left: pointer.x,
        top: pointer.y,
        width: 0,
        height: 0,
        fill: "transparent",
        stroke: currentColor,
        strokeWidth: getThickness(),
        strokeUniform: true,
        selectable: false,
        evented: false,
      });
      canvas.add(activeShape);
    } else if (currentTool === "ellipse") {
      activeShape = new fabric.Ellipse({
        left: pointer.x,
        top: pointer.y,
        rx: 0,
        ry: 0,
        fill: "transparent",
        stroke: currentColor,
        strokeWidth: getThickness(),
        strokeUniform: true,
        selectable: false,
        evented: false,
      });
      canvas.add(activeShape);
    } else if (currentTool === "arrow" || currentTool === "line") {
      activeShape = new fabric.Line(
        [pointer.x, pointer.y, pointer.x, pointer.y],
        {
          stroke: currentColor,
          strokeWidth: getThickness(),
          selectable: false,
          evented: false,
        }
      );
      canvas.add(activeShape);
    } else if (currentTool === "mosaic") {
      // Mosaic: just track the start; we draw on mouse up
      activeShape = null;
    }
  }

  function onMouseMove(opt) {
    if (!isDrawing || !drawStart) return;
    var pointer = canvas.getViewportPoint(opt.e);

    if (currentTool === "rect" && activeShape) {
      var left = Math.min(drawStart.x, pointer.x);
      var top = Math.min(drawStart.y, pointer.y);
      var width = Math.abs(pointer.x - drawStart.x);
      var height = Math.abs(pointer.y - drawStart.y);
      activeShape.set({ left: left, top: top, width: width, height: height });
      canvas.renderAll();
    } else if (currentTool === "ellipse" && activeShape) {
      var left2 = Math.min(drawStart.x, pointer.x);
      var top2 = Math.min(drawStart.y, pointer.y);
      var rx = Math.abs(pointer.x - drawStart.x) / 2;
      var ry = Math.abs(pointer.y - drawStart.y) / 2;
      activeShape.set({ left: left2, top: top2, rx: rx, ry: ry });
      canvas.renderAll();
    } else if (
      (currentTool === "arrow" || currentTool === "line") &&
      activeShape
    ) {
      activeShape.set({ x2: pointer.x, y2: pointer.y });
      canvas.renderAll();
    }
    // mosaic: nothing to draw during drag (could show selection rect later)
  }

  function onMouseUp(opt) {
    if (!isDrawing) return;
    isDrawing = false;

    var pointer = canvas.getViewportPoint(opt.e);

    if (currentTool === "arrow" && activeShape) {
      // Replace the plain line with line + arrowhead group
      var x1 = activeShape.x1;
      var y1 = activeShape.y1;
      var x2 = activeShape.x2;
      var y2 = activeShape.y2;
      canvas.remove(activeShape);

      if (Math.abs(x2 - x1) > 2 || Math.abs(y2 - y1) > 2) {
        createArrow(x1, y1, x2, y2);
      }
    } else if (currentTool === "mosaic") {
      // Apply mosaic effect in the dragged region
      if (drawStart) {
        var mx1 = Math.min(drawStart.x, pointer.x);
        var my1 = Math.min(drawStart.y, pointer.y);
        var mw = Math.abs(pointer.x - drawStart.x);
        var mh = Math.abs(pointer.y - drawStart.y);
        if (mw > 4 && mh > 4) {
          applyMosaic(mx1, my1, mw, mh);
        }
      }
    } else if (activeShape) {
      // For rect, ellipse, line — make them selectable now
      activeShape.set({ selectable: true, evented: true });
      canvas.setActiveObject(activeShape);
    }

    activeShape = null;
    drawStart = null;
    saveState();
  }

  // ── Arrow Tool ──

  function createArrow(x1, y1, x2, y2) {
    var sw = getThickness();
    var headWidth = Math.max(sw * 6, 18);
    var headHeight = Math.max(sw * 8, 24);
    var angle = Math.atan2(y2 - y1, x2 - x1);

    // Shorten the line so it doesn't poke through the arrowhead
    var shortenBy = headHeight * 0.4;
    var lx2 = x2 - Math.cos(angle) * shortenBy;
    var ly2 = y2 - Math.sin(angle) * shortenBy;

    var line = new fabric.Line([x1, y1, lx2, ly2], {
      stroke: currentColor,
      strokeWidth: sw,
      selectable: false,
      evented: false,
    });

    var head = new fabric.Triangle({
      left: x2,
      top: y2,
      width: headWidth,
      height: headHeight,
      fill: currentColor,
      selectable: false,
      evented: false,
      angle: (angle * 180) / Math.PI + 90,
      originX: "center",
      originY: "center",
    });

    // Group line + arrowhead
    var group = new fabric.Group([line, head], {
      selectable: true,
      evented: true,
    });
    canvas.add(group);
    canvas.setActiveObject(group);
  }

  // ── Mosaic Tool ──

  function applyMosaic(x, y, w, h) {
    if (!hiddenCtx) return;

    var blockSize = MOSAIC_BLOCK[currentThickness] || 12;

    // Clamp to canvas bounds
    var cx = Math.max(0, Math.round(x));
    var cy = Math.max(0, Math.round(y));
    var cw = Math.min(Math.round(w), canvas.width - cx);
    var ch = Math.min(Math.round(h), canvas.height - cy);

    if (cw <= 0 || ch <= 0) return;

    // Read pixels from hidden canvas (original background)
    var imageData = hiddenCtx.getImageData(cx, cy, cw, ch);
    var data = imageData.data;

    // Create a temporary canvas for the pixelated result
    var tmpCanvas = document.createElement("canvas");
    tmpCanvas.width = cw;
    tmpCanvas.height = ch;
    var tmpCtx = tmpCanvas.getContext("2d");

    // Pixelate: for each block, compute average color and fill
    for (var by = 0; by < ch; by += blockSize) {
      for (var bx = 0; bx < cw; bx += blockSize) {
        var bw = Math.min(blockSize, cw - bx);
        var bh = Math.min(blockSize, ch - by);
        var r = 0,
          g = 0,
          b = 0,
          count = 0;

        for (var py = by; py < by + bh; py++) {
          for (var px = bx; px < bx + bw; px++) {
            var idx = (py * cw + px) * 4;
            r += data[idx];
            g += data[idx + 1];
            b += data[idx + 2];
            count++;
          }
        }

        r = Math.round(r / count);
        g = Math.round(g / count);
        b = Math.round(b / count);

        tmpCtx.fillStyle = "rgb(" + r + "," + g + "," + b + ")";
        tmpCtx.fillRect(bx, by, bw, bh);
      }
    }

    // Create fabric Image from the pixelated canvas
    var mosaicImg = new fabric.FabricImage(tmpCanvas, {
      left: cx,
      top: cy,
      selectable: true,
      evented: true,
    });
    canvas.add(mosaicImg);
    canvas.setActiveObject(mosaicImg);
  }

  // ── Text Tool ──

  function placeText(pointer) {
    var text = new fabric.IText("", {
      left: pointer.x,
      top: pointer.y,
      fontFamily: "-apple-system, BlinkMacSystemFont, sans-serif",
      fontSize: 16 + getThickness() * 2,
      fill: currentColor,
      selectable: true,
      evented: true,
    });
    canvas.add(text);
    canvas.setActiveObject(text);
    text.enterEditing();

    // Save state when editing exits
    text.on("editing:exited", function () {
      // Remove empty text objects
      if (!text.text || text.text.trim() === "") {
        canvas.remove(text);
      }
      saveState();
    });
  }

  // ── Number Marker Tool ──

  function placeNumber(pointer) {
    var radius = 12;
    var circle = new fabric.Circle({
      radius: radius,
      fill: currentColor,
      originX: "center",
      originY: "center",
      selectable: false,
      evented: false,
    });

    var label = new fabric.Text(String(numberCounter), {
      fontSize: 14,
      fill: "#ffffff",
      fontFamily: "-apple-system, BlinkMacSystemFont, sans-serif",
      fontWeight: "bold",
      originX: "center",
      originY: "center",
      selectable: false,
      evented: false,
    });

    var group = new fabric.Group([circle, label], {
      left: pointer.x,
      top: pointer.y,
      originX: "center",
      originY: "center",
      selectable: true,
      evented: true,
    });

    canvas.add(group);
    canvas.setActiveObject(group);
    numberCounter++;
    saveState();
  }

  // ── Undo / Redo ──

  function saveState() {
    if (savingState || !canvas) return;
    savingState = true;

    // Save only objects, not the background image (which never changes
    // and would bloat each state entry by several MB on Retina screens).
    var objects = canvas.toJSON().objects || [];

    // Trim any redo states ahead of current index
    if (stateIndex < stateStack.length - 1) {
      stateStack = stateStack.slice(0, stateIndex + 1);
    }

    stateStack.push(objects);

    // Enforce max stack depth
    if (stateStack.length > MAX_STACK) {
      stateStack.shift();
    }

    stateIndex = stateStack.length - 1;
    savingState = false;
    updateUndoRedoButtons();
  }

  function undo() {
    if (stateIndex <= 0 || !canvas) return;
    stateIndex--;
    restoreState(stateStack[stateIndex]);
  }

  function redo() {
    if (stateIndex >= stateStack.length - 1 || !canvas) return;
    stateIndex++;
    restoreState(stateStack[stateIndex]);
  }

  function restoreState(objects) {
    if (!canvas) return;
    savingState = true;

    // Clear all objects but preserve the background image
    canvas.remove.apply(canvas, canvas.getObjects());
    fabric.util.enlivenObjects(objects).then(function (enlivened) {
      for (var i = 0; i < enlivened.length; i++) {
        canvas.add(enlivened[i]);
      }
      canvas.renderAll();
      savingState = false;
      updateUndoRedoButtons();
    });
  }

  function updateUndoRedoButtons() {
    var undoBtn = document.getElementById("btn-undo");
    var redoBtn = document.getElementById("btn-redo");
    if (undoBtn) undoBtn.disabled = stateIndex <= 0;
    if (redoBtn) redoBtn.disabled = stateIndex >= stateStack.length - 1;
  }

  // ── Tool Activation ──

  function activateTool(tool) {
    // Deactivate previous tool
    deactivateCurrentTool();

    if (currentTool === tool) {
      // Toggle off — clicking the same tool deselects it
      currentTool = null;
      updateToolbarUI();
      return;
    }

    currentTool = tool;
    updateToolbarUI();

    if (tool === "pen") {
      canvas.isDrawingMode = true;
      canvas.freeDrawingBrush = new fabric.PencilBrush(canvas);
      canvas.freeDrawingBrush.color = currentColor;
      canvas.freeDrawingBrush.width = getThickness();
    } else {
      canvas.isDrawingMode = false;
    }

    if (tool === "text") {
      document
        .querySelector(".canvas-container")
        .classList.add("text-cursor");
    }

    // Disable object selection while a tool is active
    canvas.forEachObject(function (obj) {
      obj.selectable = false;
      obj.evented = false;
    });
    canvas.discardActiveObject();
    canvas.renderAll();
  }

  function deactivateCurrentTool() {
    if (!canvas) return;

    canvas.isDrawingMode = false;
    isDrawing = false;
    activeShape = null;
    drawStart = null;

    var cc = document.querySelector(".canvas-container");
    if (cc) cc.classList.remove("text-cursor");

    // Re-enable object selection
    if (canvas) {
      canvas.forEachObject(function (obj) {
        if (obj !== bgImage) {
          obj.selectable = true;
          obj.evented = true;
        }
      });
    }
  }

  function updateToolbarUI() {
    // Update active state on tool buttons
    var buttons = document.querySelectorAll(".tool-btn[data-tool]");
    for (var i = 0; i < buttons.length; i++) {
      if (buttons[i].getAttribute("data-tool") === currentTool) {
        buttons[i].classList.add("active");
      } else {
        buttons[i].classList.remove("active");
      }
    }

    // Show/hide secondary panel
    var panel = document.getElementById("secondary-panel");
    if (currentTool && currentTool !== "number") {
      // Number tool doesn't need thickness
      panel.classList.remove("hidden");
    } else if (currentTool === "number") {
      // Number still shows color, hide thickness? Keep both for simplicity.
      panel.classList.remove("hidden");
    } else {
      panel.classList.add("hidden");
    }
  }

  // ── Helpers ──

  function getThickness() {
    return THICKNESS[currentThickness] || 4;
  }

  // ── Toolbar Event Delegation ──

  // Tool buttons
  document.getElementById("toolbar").addEventListener("click", function (e) {
    var btn = e.target.closest(".tool-btn");
    if (!btn) return;

    var tool = btn.getAttribute("data-tool");
    if (tool) {
      activateTool(tool);
      return;
    }

    // Undo / Redo
    if (btn.id === "btn-undo") {
      undo();
      return;
    }
    if (btn.id === "btn-redo") {
      redo();
      return;
    }

    // Actions
    if (btn.id === "btn-save") {
      wz.send("save");
      return;
    }
    if (btn.id === "btn-cancel") {
      wz.send("cancel");
      return;
    }
    if (btn.id === "btn-confirm") {
      wz.send("confirm");
      return;
    }
  });

  // Color dots
  document
    .getElementById("color-section")
    .addEventListener("click", function (e) {
      var dot = e.target.closest(".color-dot");
      if (!dot) return;

      // Update selection
      var dots = document.querySelectorAll(".color-dot");
      for (var i = 0; i < dots.length; i++) dots[i].classList.remove("selected");
      dot.classList.add("selected");

      currentColor = dot.getAttribute("data-color");

      // Update brush if pen is active
      if (currentTool === "pen" && canvas && canvas.freeDrawingBrush) {
        canvas.freeDrawingBrush.color = currentColor;
      }
    });

  // Thickness buttons
  document
    .getElementById("thickness-section")
    .addEventListener("click", function (e) {
      var btn = e.target.closest(".thickness-btn");
      if (!btn) return;

      // Update selection
      var buttons = document.querySelectorAll(".thickness-btn");
      for (var i = 0; i < buttons.length; i++)
        buttons[i].classList.remove("selected");
      btn.classList.add("selected");

      currentThickness = btn.getAttribute("data-thickness");

      // Update brush if pen is active
      if (currentTool === "pen" && canvas && canvas.freeDrawingBrush) {
        canvas.freeDrawingBrush.width = getThickness();
      }
    });

  // ── Keyboard Shortcuts ──

  document.addEventListener("keydown", function (e) {
    // Cmd+Shift+Z = redo (check before Cmd+Z since Shift changes key to "Z")
    if (e.metaKey && e.shiftKey && (e.key === "z" || e.key === "Z")) {
      e.preventDefault();
      redo();
      return;
    }
    // Cmd+Z = undo
    if (e.metaKey && !e.shiftKey && e.key === "z") {
      e.preventDefault();
      undo();
      return;
    }

    // Esc = cancel (but not while editing text)
    if (e.key === "Escape") {
      // If editing text, just exit editing mode
      var activeObj = canvas && canvas.getActiveObject();
      if (activeObj && activeObj.isEditing) {
        activeObj.exitEditing();
        return;
      }
      wz.send("cancel");
      return;
    }

    // Enter = confirm (but not while editing text)
    if (e.key === "Enter") {
      var activeObj2 = canvas && canvas.getActiveObject();
      if (activeObj2 && activeObj2.isEditing) {
        // Let Enter work normally in text editing
        return;
      }
      wz.send("confirm");
      return;
    }
  });
})();
