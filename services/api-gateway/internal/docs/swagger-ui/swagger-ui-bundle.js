(function () {
  var TOKEN_KEY = "estategap-docs-token";

  function slugify(input) {
    return String(input || "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "");
  }

  function byTag(spec) {
    var groups = {};
    var tags = spec.tags || [];
    Object.keys(spec.paths || {}).forEach(function (path) {
      var methods = spec.paths[path];
      Object.keys(methods || {}).forEach(function (method) {
        var operation = methods[method];
        var tag = (operation.tags && operation.tags[0]) || "General";
        if (!groups[tag]) {
          var tagMeta = tags.find(function (item) { return item.name === tag; }) || {};
          groups[tag] = {
            name: tag,
            description: tagMeta.description || "",
            operations: []
          };
        }
        groups[tag].operations.push({
          method: method.toUpperCase(),
          path: path,
          operation: operation
        });
      });
    });
    return Object.keys(groups).sort().map(function (key) { return groups[key]; });
  }

  function firstExample(node) {
    if (!node) {
      return "";
    }
    if (node.example !== undefined) {
      return JSON.stringify(node.example, null, 2);
    }
    if (node.examples) {
      var first = Object.keys(node.examples)[0];
      if (first && node.examples[first] && node.examples[first].value !== undefined) {
        return JSON.stringify(node.examples[first].value, null, 2);
      }
    }
    if (node.schema && node.schema.example !== undefined) {
      return JSON.stringify(node.schema.example, null, 2);
    }
    return "";
  }

  function parameterInputs(parameters, identifier) {
    return (parameters || []).map(function (parameter, index) {
      var key = "param-" + identifier + "-" + index;
      return [
        '<div class="eg-field">',
        "<label for=\"" + key + "\">" + parameter.name + " (" + parameter.in + ")</label>",
        "<input id=\"" + key + "\" data-location=\"" + parameter.in + "\" data-name=\"" + parameter.name + "\" placeholder=\"" + (parameter.description || "") + "\" />",
        "</div>"
      ].join("");
    }).join("");
  }

  function requestBodyInput(operation, identifier) {
    var body = operation.requestBody && operation.requestBody.content && operation.requestBody.content["application/json"];
    if (!body) {
      return "";
    }
    var example = firstExample(body);
    var key = "body-" + identifier;
    return [
      '<div class="eg-field">',
      "<label for=\"" + key + "\">Request body</label>",
      "<textarea id=\"" + key + "\" data-body=\"true\">" + escapeHTML(example || "{}") + "</textarea>",
      "</div>"
    ].join("");
  }

  function executeOperation(root, spec, item, identifier) {
    var section = root.querySelector("[data-operation=\"" + identifier + "\"]");
    var responseBox = section.querySelector("[data-response]");
    var button = section.querySelector("[data-run]");
    var inputs = section.querySelectorAll("input[data-name]");
    var bodyInput = section.querySelector("textarea[data-body]");
    var token = root.querySelector("#eg-token").value.trim();
    var url = new URL(item.path, window.location.origin);

    inputs.forEach(function (input) {
      if (!input.value) {
        return;
      }
      if (input.dataset.location === "path") {
        url.pathname = url.pathname.replace("{" + input.dataset.name + "}", encodeURIComponent(input.value));
        return;
      }
      if (input.dataset.location === "query") {
        url.searchParams.set(input.dataset.name, input.value);
      }
    });

    var headers = {
      Accept: "application/json"
    };
    if (token) {
      headers.Authorization = "Bearer " + token;
      localStorage.setItem(TOKEN_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_KEY);
    }

    var request = {
      method: item.method,
      headers: headers
    };
    if (bodyInput) {
      headers["Content-Type"] = "application/json";
      request.body = bodyInput.value || "{}";
    }

    responseBox.classList.remove("bad");
    responseBox.textContent = "Requesting " + url.pathname + "...";
    button.disabled = true;

    fetch(url, request)
      .then(function (response) {
        return response.text().then(function (body) {
          var payload = body;
          try {
            payload = JSON.stringify(JSON.parse(body), null, 2);
          } catch (error) {
            if (!body) {
              payload = "<empty>";
            }
          }
          if (!response.ok) {
            responseBox.classList.add("bad");
          }
          responseBox.textContent = [
            response.status + " " + response.statusText,
            "",
            payload
          ].join("\n");
        });
      })
      .catch(function (error) {
        responseBox.classList.add("bad");
        responseBox.textContent = "Request failed\n\n" + error.message;
      })
      .finally(function () {
        button.disabled = false;
      });
  }

  function escapeHTML(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function render(root, spec, config) {
    var token = config.persistAuthorization ? (localStorage.getItem(TOKEN_KEY) || "") : "";
    var groups = byTag(spec);
    root.innerHTML = [
      '<div class="eg-shell">',
      '<section class="eg-hero">',
      '<p class="eg-eyebrow">Interactive API Reference</p>',
      '<h1 class="eg-title">' + escapeHTML(spec.info && spec.info.title ? spec.info.title : "API Docs") + "</h1>",
      '<p class="eg-description">' + escapeHTML(spec.info && spec.info.description ? spec.info.description : "Explore the API and run live calls.") + "</p>",
      '<div class="eg-toolbar">',
      '<div><span class="eg-tag">Live OpenAPI</span></div>',
      '<div><label for="eg-token">Bearer token</label><input id="eg-token" placeholder="Paste a JWT to enable authenticated calls" value="' + escapeHTML(token) + '" /></div>',
      '</div>',
      '</section>',
      '<div class="eg-grid">',
      groups.length ? groups.map(function (group) {
        return [
          '<section class="eg-tag-section">',
          '<div class="eg-tag-header"><h2>' + escapeHTML(group.name) + "</h2><p>" + escapeHTML(group.description) + "</p></div>",
          group.operations.map(function (item) {
            var identifier = slugify(item.method + "-" + item.path);
            var operation = item.operation || {};
            return [
              '<details class="eg-operation" id="' + identifier + '" data-operation="' + identifier + '">',
              "<summary>",
              '<div class="eg-operation-head">',
              '<span class="eg-method eg-method-' + item.method.toLowerCase() + '">' + item.method + "</span>",
              '<span class="eg-operation-path">' + escapeHTML(item.path) + "</span>",
              "</div>",
              '<h3 class="eg-operation-title">' + escapeHTML(operation.summary || operation.operationId || item.path) + "</h3>",
              '<p class="eg-operation-description">' + escapeHTML(operation.description || "") + "</p>",
              "</summary>",
              '<div class="eg-operation-body">',
              '<div class="eg-operation-grid">' + parameterInputs(operation.parameters, identifier) + requestBodyInput(operation, identifier) + "</div>",
              '<div class="eg-actions"><button class="eg-button" type="button" data-run="true">Try it out</button></div>',
              '<pre class="eg-response" data-response>Ready.</pre>',
              "</div>",
              "</details>"
            ].join("");
          }).join(""),
          "</section>"
        ].join("");
      }).join("") : '<div class="eg-empty">No paths were found in the OpenAPI spec.</div>',
      "</div>",
      "</div>"
    ].join("");

    root.querySelectorAll("[data-run]").forEach(function (button) {
      button.addEventListener("click", function () {
        var operationRoot = button.closest("[data-operation]");
        executeOperation(root, spec, findOperation(groups, operationRoot.dataset.operation), operationRoot.dataset.operation);
      });
    });

    if (config.deepLinking && window.location.hash) {
      var target = root.querySelector(window.location.hash);
      if (target) {
        target.open = true;
        target.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    }
  }

  function findOperation(groups, identifier) {
    for (var i = 0; i < groups.length; i += 1) {
      for (var j = 0; j < groups[i].operations.length; j += 1) {
        var item = groups[i].operations[j];
        if (slugify(item.method + "-" + item.path) === identifier) {
          return item;
        }
      }
    }
    return { method: "GET", path: "/" };
  }

  window.SwaggerUIBundle = function SwaggerUIBundle(config) {
    var root = document.querySelector(config.dom_id || "#swagger-ui");
    if (!root) {
      return null;
    }
    root.innerHTML = '<div class="eg-shell"><div class="eg-empty">Loading OpenAPI spec...</div></div>';
    fetch(config.url)
      .then(function (response) { return response.json(); })
      .then(function (spec) { render(root, spec, config || {}); })
      .catch(function (error) {
        root.innerHTML = '<div class="eg-shell"><div class="eg-empty">Failed to load docs: ' + escapeHTML(error.message) + "</div></div>";
      });
    return null;
  };
}());
