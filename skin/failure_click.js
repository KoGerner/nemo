/* "What if this fails?" (ticket 254): nemo's own click mode over the grouped graph's lens.
   graph.js comes from bia-workflow-g150, pinned by bytes and never edited, so this script runs
   after it on the same page and wraps two of its globals: keepSet (what stays lit) and applyLens
   (which repaints). With the mode on, clicking a resource marks it failed: the resource turns red,
   every resource that stands on it stays lit with the arrows between them, and every activity it
   reaches is marked hit, dependent activities (processes) listed first. A second click on the
   same resource, Clear or Esc resets it. Read-only (ADR-0004): no request, no model, no write.
   Everything is read from the island lists dep_graph.py precomputed; nothing here derives an edge.
   Ticket 262: the reach goes on down the process chain. Each process and activity it hits adds
   the process cards its `flows_to` names, which draw read off the room's process map, already
   followed to the end; they join the dependent activities, after the ones hit directly.
   Ticket 263: below what it hits, the failed resource says how soon it is needed back, whose MTPD
   sets that, where its register row states another figure, and every RTO too slow for it, all
   from the `needs` draw computed (needs.py); nothing here compares a figure.
   Ticket 269: g150's facts panel shows names, not ids (fillFacts, below); ticket 270: no code;
   ticket 274: an owner written for the demo says so, and a gap says why. */
var failMode = false;

function failure() {  // the failed resource and what it hits, or null
  var n = failMode && lens.type === 'focus' ? byId[lens.value] : null;
  if (!n || (n.kind !== 'asset' && n.kind !== 'unmodeled')) return null;
  var down = [n.id].concat(n.impact || []);  // the resource and everything standing on it
  var procs = [], acts = [];
  down.forEach(function (id) {
    var d = byId[id] || {};
    (d.procs || []).forEach(function (p) { if (procs.indexOf(p) < 0) procs.push(p); });
    (d.acts || []).forEach(function (a) { if (acts.indexOf(a) < 0) acts.push(a); });
  });
  procs.concat(acts).forEach(function (id) {
    ((byId[id] || {}).flows_to || []).forEach(function (p) {
      if (procs.indexOf(p) < 0) procs.push(p);
    });
  });
  return {node: n, down: down, procs: procs, acts: acts};
}

var lensKeep = keepSet;
keepSet = function () {
  var f = failure();
  if (!f) return lensKeep();
  var keep = Object.create(null);
  f.down.concat(f.procs, f.acts).forEach(function (id) { keep[id] = true; });
  // the group card stands in for the folded processes: kept, it unfolds the band
  if (f.procs.length && byId['group:processes']) keep['group:processes'] = true;
  return keep;
};

function named(title, ids) {  // graph.js's section(), names only: the owner reads no ids here
  facts.appendChild(el('h3', null, title + ' (' + ids.length + ')'));
  if (!ids.length) { facts.appendChild(el('p', 'hint', 'None recorded.')); return; }
  var ul = el('ul');
  ids.forEach(function (id) {
    var name = parts(byId[id] || {id: id})[0], li = el('li'), b = press('focus', id, name);
    b.title = name;
    li.appendChild(b);
    ul.appendChild(li);
  });
  facts.appendChild(ul);
}

// Ticket 269: g150's panel, re-labelled once filled. An activity's "Record id" row goes, and so
// does the muted "<id or dept> ·" opening each list entry; the entry's button keeps its id.
// Ticket 270: a resource's "Asset id" row goes too, and a department is called by the name draw
// put on the card (`dept_name`), in its row and in an activity's "Dependent activities in" list.
// Ticket 271: a resource's own "Dependent activities" list (direct links only) reads "Activities
// that depend on it directly", so it no longer seems to contradict the failure's chain-wide count.
// Ticket 274: a gap gives its reason (`owner_gap`) in the badge. The card keeps its OWNER MISSING
// badge and gains no owner line. ADR-0048 (ticket 354): the graph carries no "for the demo" mark,
// so an owner written for the demo reads as any other; the register keeps `owner_evidence`.
var lensFacts = fillFacts;
fillFacts = function () {
  lensFacts();
  var n = lens.type === 'focus' ? byId[lens.value] : null;
  facts.querySelectorAll('tr').forEach(function (tr) {
    var key = tr.firstChild && tr.firstChild.textContent;
    if (key === 'Record id' || key === 'Asset id') tr.remove();
    else if (key === 'Department' && n && n.dept_name) tr.lastChild.textContent = n.dept_name;
    else if (key === 'Owner' && n) {
      var badge = tr.lastChild.querySelector('.badge');
      if (badge && n.owner_gap) badge.textContent = 'OWNER MISSING: ' + n.owner_gap;
    }
  });
  facts.querySelectorAll('li > span.mut').forEach(function (s) { s.remove(); });
  var was = n && n.dept_name ? 'Dependent activities in ' + n.dept + ' (' : null;
  var direct = n && n.kind === 'asset' ? 'Dependent activities (' : null;
  facts.querySelectorAll('h3').forEach(function (h) {
    if (was && h.textContent.indexOf(was) === 0) {
      h.textContent = 'Dependent activities in ' + n.dept_name + ' (' + h.textContent.slice(was.length);
    } else if (direct && h.textContent.indexOf(direct) === 0) {
      h.textContent = 'Activities that depend on it directly (' + h.textContent.slice(direct.length);
    }
  });
};

var lensPaint = applyLens;
applyLens = function () {
  lensPaint();
  var f = failure();
  var hit = Object.create(null);
  if (f) f.procs.concat(f.acts).forEach(function (id) { hit[id] = true; });
  document.querySelectorAll('.node').forEach(function (e) {
    e.classList.toggle('failed', !!f && e.dataset.id === f.node.id);
    e.classList.toggle('hit', !!hit[e.dataset.id]);
  });
  document.body.classList.toggle('failing', !!f);
  document.getElementById('fail-clear').hidden = !f;
  if (!f) return;
  var lens0 = Array.prototype.slice.call(facts.childNodes);  // the lens's own facts go below
  facts.textContent = '';
  facts.appendChild(el('h2', 'failed', 'If ' + parts(f.node)[0] + ' fails'));
  named('Dependent activities it hits', f.procs);
  named('BIA activities it hits', f.acts);
  var need = f.node.needs || {};
  if (need.within) {
    facts.appendChild(el('p', 'need', 'Needed back within ' + need.within + ': ' + need.set_by
                                      + "'s " + need.mtpd + ' MTPD'));
  }
  if (need.register) {
    facts.appendChild(el('p', 'need', "Last year's record says " + need.register
                                      + "; this year's BIA says " + need.within + '.'));
  }
  (need.flags || []).forEach(function (g) {
    facts.appendChild(el('p', 'too-slow', 'Too slow: ' + g.who + "'s RTO " + g.rto
                                          + ' is not inside ' + g.activity + "'s MTPD " + g.mtpd + '.'));
  });
  facts.appendChild(el('hr'));
  lens0.forEach(function (c) { facts.appendChild(c); });
};

(function () {  // the arrowhead, and the mode's two controls at the head of the page's toolbar
  // Every edge runs from what needs to what is needed (consumes: resource to process), so the
  // arrowhead sits at whichever end the failure flows into (failure_click.css picks the end).
  var ns = 'http://www.w3.org/2000/svg';
  var defs = document.createElementNS(ns, 'defs'), mark = document.createElementNS(ns, 'marker');
  var head = document.createElementNS(ns, 'path');
  [['id', 'fail-arrow'], ['viewBox', '0 0 10 10'], ['refX', '9'], ['refY', '5'],
   ['markerWidth', '7'], ['markerHeight', '7'], ['orient', 'auto-start-reverse']]
    .forEach(function (a) { mark.setAttribute(a[0], a[1]); });
  head.setAttribute('d', 'M0,0 L10,5 L0,10 z');
  head.style.fill = 'var(--color-rust)';
  mark.appendChild(head); defs.appendChild(mark);
  document.querySelector('#canvas svg').prepend(defs);
  var bar = document.getElementById('toolbar');
  var mode = el('button', null, 'What if it fails?');
  mode.type = 'button'; mode.id = 'fail-mode'; mode.setAttribute('aria-pressed', 'false');
  var clear = el('button', null, 'Clear');
  clear.type = 'button'; clear.id = 'fail-clear'; clear.hidden = true;
  bar.insertBefore(clear, bar.firstChild);
  bar.insertBefore(mode, clear);
  mode.addEventListener('click', function () {
    failMode = !failMode;
    mode.setAttribute('aria-pressed', String(failMode));
    document.body.classList.toggle('fail-mode', failMode);
    applyLens();
  });
  clear.addEventListener('click', function () { setLens('none'); });
  // A second click on the failed resource clears it. Capture phase, so graph.js never sees it
  // and re-focuses; the tail of a drag is left to graph.js, which drops it.
  document.addEventListener('click', function (ev) {
    var f = failure(), t = ev.target;
    if (!f || moved || !t || !t.closest) return;
    var node = t.closest('.node');
    if (node && node.dataset.id === f.node.id) { ev.stopPropagation(); setLens('none'); }
  }, true);
})();
