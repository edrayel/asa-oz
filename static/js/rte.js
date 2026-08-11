/* TinyRich — dependency-free rich text editor. Initialize on any textarea with [data-rte]. */
(function () {
  'use strict';

  var TOOLBAR = [
    { cmd: 'bold', icon: 'B', title: 'Bold (Ctrl+B)' },
    { cmd: 'italic', icon: 'I', title: 'Italic (Ctrl+I)' },
    { cmd: 'underline', icon: 'U', title: 'Underline (Ctrl+U)' },
    { cmd: 'strikeThrough', icon: 'S', title: 'Strikethrough' },
    'sep',
    { cmd: 'formatBlock', arg: 'P', icon: '¶', title: 'Paragraph' },
    { cmd: 'formatBlock', arg: 'H2', icon: 'H2', title: 'Heading' },
    { cmd: 'formatBlock', arg: 'H3', icon: 'H3', title: 'Subheading' },
    { cmd: 'formatBlock', arg: 'BLOCKQUOTE', icon: '❝', title: 'Quote' },
    'sep',
    { cmd: 'insertUnorderedList', icon: '•', title: 'Bullet list' },
    { cmd: 'insertOrderedList', icon: '1.', title: 'Numbered list' },
    'sep',
    { cmd: 'createLink', icon: '🔗', prompt: 'Link URL:', title: 'Insert link' },
    { cmd: 'unlink', icon: '⛓', title: 'Remove link' },
    'sep',
    { cmd: 'removeFormat', icon: '⌫', title: 'Clear formatting' },
    { cmd: 'source', icon: '</>', title: 'Toggle HTML source' },
  ];

  function esc(s) {
    var d = document.createElement('div');
    d.textContent = s == null ? '' : String(s);
    return d.innerHTML;
  }

  function buildToolbar(editor) {
    var tb = document.createElement('div');
    tb.className = 'rte-toolbar';
    TOOLBAR.forEach(function (tool) {
      if (tool === 'sep') {
        var sep = document.createElement('span');
        sep.className = 'rte-sep';
        tb.appendChild(sep);
        return;
      }
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.innerHTML = tool.icon;
      btn.title = tool.title;
      btn.setAttribute('data-cmd', tool.cmd);
      if (tool.arg) btn.setAttribute('data-arg', tool.arg);
      if (tool.prompt) btn.setAttribute('data-prompt', tool.prompt);
      btn.addEventListener('mousedown', function (e) {
        e.preventDefault();
        if (tool.cmd === 'source') {
          editor.root.classList.toggle('rte-source-on');
          return;
        }
        if (tool.cmd === 'createLink') {
          var url = prompt(tool.prompt || 'URL:', 'https://');
          if (!url) return;
          document.execCommand('createLink', false, url);
        } else {
          document.execCommand(tool.cmd, false, tool.arg || null);
        }
        editor.sync();
        editor.updateActive();
      });
      tb.appendChild(btn);
    });
    return tb;
  }

  function TinyRich(textarea) {
    if (textarea._rte) return textarea._rte;
    var root = document.createElement('div');
    root.className = 'rte';

    var source = document.createElement('textarea');
    source.className = 'rte-source';
    source.value = textarea.value;

    var editor = document.createElement('div');
    editor.className = 'rte-editor';
    editor.contentEditable = 'true';
    editor.innerHTML = textarea.value;

    var toolbar = buildToolbar({ root: root });

    root.appendChild(toolbar);
    root.appendChild(editor);
    root.appendChild(source);

    textarea.style.display = 'none';
    textarea.parentNode.insertBefore(root, textarea);
    root.appendChild(textarea);

    var inst = {
      root: root, editor: editor, source: source, textarea: textarea,
      sync: function () {
        var html = editor.innerHTML;
        textarea.value = html;
        source.value = html;
      },
      updateActive: function () {
        toolbar.querySelectorAll('button[data-cmd]').forEach(function (btn) {
          var cmd = btn.getAttribute('data-cmd');
          if (cmd === 'source') return;
          try {
            btn.classList.toggle('active', document.queryCommandState(cmd));
          } catch (e) {}
        });
      }
    };
    editor._rte = inst;
    textarea._rte = inst;

    editor.addEventListener('input', function () { inst.sync(); });
    editor.addEventListener('keyup', function () { inst.updateActive(); });
    editor.addEventListener('mouseup', function () { inst.updateActive(); });
    editor.addEventListener('keydown', function (e) {
      if ((e.ctrlKey || e.metaKey) && !e.shiftKey && !e.altKey) {
        var map = { 'b': 'bold', 'i': 'italic', 'u': 'underline' };
        var cmd = map[e.key.toLowerCase()];
        if (cmd) { e.preventDefault(); document.execCommand(cmd, false, null); inst.sync(); inst.updateActive(); }
      }
    });
    source.addEventListener('input', function () {
      editor.innerHTML = source.value;
      textarea.value = source.value;
    });
    return inst;
  }

  function initAll() {
    document.querySelectorAll('textarea[data-rte]').forEach(function (ta) {
      if (!ta._rte) TinyRich(ta);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAll);
  } else {
    initAll();
  }
  document.addEventListener('htmx:afterSwap', initAll);
  window.TinyRich = TinyRich;
  window.TinyRich.init = initAll;
})();
