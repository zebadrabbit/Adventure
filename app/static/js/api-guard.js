/*
 * project: Adventure MUD
 * module: api-guard.js
 *
 * Global fetch wrapper: stamps an `X-Requested-With: XMLHttpRequest` header
 * on every same-origin request. The server rejects mutating /api/ requests
 * without it (see `_require_api_header` in app/__init__.py) — browsers will
 * not attach custom headers to cross-site requests without a CORS preflight,
 * so this blocks cross-site request forgery against the JSON API.
 *
 * Loaded from the <head> of base.html / admin_base_new.html so it wraps
 * fetch before any page script runs.
 */
(function () {
  "use strict";

  var HEADER = "X-Requested-With";
  var VALUE = "XMLHttpRequest";
  var nativeFetch = window.fetch;
  if (!nativeFetch) return;

  function sameOrigin(url) {
    try {
      return new URL(url, window.location.href).origin === window.location.origin;
    } catch (e) {
      return false;
    }
  }

  window.fetch = function (input, init) {
    var url = typeof input === "string" ? input : (input && input.url) || "";
    if (sameOrigin(url)) {
      if (input instanceof Request && !init) {
        var reqHeaders = new Headers(input.headers);
        reqHeaders.set(HEADER, VALUE);
        input = new Request(input, { headers: reqHeaders });
      } else {
        init = init || {};
        var headers = new Headers(init.headers || (input instanceof Request ? input.headers : undefined));
        headers.set(HEADER, VALUE);
        init.headers = headers;
      }
    }
    return nativeFetch.call(this, input, init);
  };
})();
