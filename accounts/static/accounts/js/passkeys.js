// Passkeys: sign in / add / rename / remove (fingerprint, face or screen lock).
// Used on the login page and on both profile pages. The profile card is loaded
// with fetch() after the page opens, so all buttons are handled by delegation.
(function () {
  "use strict";

  // ---------- helpers ----------

  function b64urlToBuf(value) {
    const base64 = value.replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64 + "===".slice((base64.length + 3) % 4);
    const binary = atob(padded);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    return bytes.buffer;
  }

  function bufToB64url(buffer) {
    const bytes = new Uint8Array(buffer);
    let binary = "";
    for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
    return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  }

  function csrfToken() {
    const match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? match[1] : "";
  }

  async function postJSON(url, data) {
    const res = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
      body: JSON.stringify(data || {}),
    });
    let body = {};
    try { body = await res.json(); } catch (e) { /* non-JSON error page */ }
    if (!res.ok || body.ok === false) {
      throw new Error(body.error || "Something went wrong. Please try again.");
    }
    return body;
  }

  function isIpHost() {
    return /^\d{1,3}(\.\d{1,3}){3}$/.test(location.hostname) || location.hostname.includes(":");
  }

  function supported() {
    return !!(window.PublicKeyCredential && navigator.credentials && window.isSecureContext);
  }

  function unsupportedMessage() {
    if (isIpHost()) return "Passkeys don't work on an IP address. Open the site at http://localhost:8000 instead.";
    return "This browser doesn't support passkeys. Use your email and password instead.";
  }

  // The browser rejects with these when the user closes the prompt or it times out
  function friendlyBrowserError(err) {
    if (err && (err.name === "NotAllowedError" || err.name === "AbortError")) {
      return "Passkey prompt was cancelled or timed out.";
    }
    if (err && err.name === "InvalidStateError") {
      return "This device already has a passkey for your account.";
    }
    return (err && err.message) || "Something went wrong. Please try again.";
  }

  function setBusy(button, busy, busyText) {
    if (!button) return;
    if (busy) {
      button.dataset.originalHtml = button.innerHTML;
      button.disabled = true;
      button.textContent = busyText;
    } else if (button.dataset.originalHtml) {
      button.innerHTML = button.dataset.originalHtml;
      button.disabled = false;
    }
  }

  function showMessage(id, text, isError) {
    const box = document.getElementById(id);
    if (!box) { if (isError) alert(text); return; }
    box.textContent = text;
    box.classList.remove("hidden", "text-red-600", "text-green-700", "bg-red-50", "bg-green-50", "border-red-200", "border-green-200");
    box.classList.add(...(isError ? ["text-red-600", "bg-red-50", "border-red-200"] : ["text-green-700", "bg-green-50", "border-green-200"]));
  }

  // ---------- sign in ----------

  async function signIn(button) {
    const urls = button.dataset;
    if (!supported()) return showMessage("passkey-login-message", unsupportedMessage(), true);

    setBusy(button, true, "Waiting for your passkey...");
    try {
      const options = await postJSON(urls.optionsUrl);
      options.challenge = b64urlToBuf(options.challenge);
      (options.allowCredentials || []).forEach(function (c) { c.id = b64urlToBuf(c.id); });

      const cred = await navigator.credentials.get({ publicKey: options });
      const result = await postJSON(urls.verifyUrl, {
        credential: {
          id: cred.id,
          rawId: bufToB64url(cred.rawId),
          type: cred.type,
          response: {
            clientDataJSON: bufToB64url(cred.response.clientDataJSON),
            authenticatorData: bufToB64url(cred.response.authenticatorData),
            signature: bufToB64url(cred.response.signature),
            userHandle: cred.response.userHandle ? bufToB64url(cred.response.userHandle) : null,
          },
          clientExtensionResults: cred.getClientExtensionResults ? cred.getClientExtensionResults() : {},
          authenticatorAttachment: cred.authenticatorAttachment || null,
        },
      });
      button.textContent = "Signed in. Redirecting...";
      window.location.href = result.redirect;
    } catch (err) {
      setBusy(button, false);
      showMessage("passkey-login-message", friendlyBrowserError(err), true);
    }
  }

  // ---------- add ----------

  function suggestDeviceName() {
    const ua = navigator.userAgent;
    if (/iPhone/.test(ua)) return "iPhone";
    if (/iPad/.test(ua)) return "iPad";
    if (/Android/.test(ua)) return "Android phone";
    if (/Windows/.test(ua)) return "Windows PC";
    if (/Macintosh/.test(ua)) return "Mac";
    return "My device";
  }

  async function addPasskey(button) {
    const urls = button.dataset;
    if (!supported()) return showMessage("passkey-card-message", unsupportedMessage(), true);

    const name = window.prompt("Name this passkey so you can recognize it later:", suggestDeviceName());
    if (name === null) return;  // cancelled

    setBusy(button, true, "Waiting for your device...");
    try {
      const options = await postJSON(urls.optionsUrl);
      options.challenge = b64urlToBuf(options.challenge);
      options.user.id = b64urlToBuf(options.user.id);
      (options.excludeCredentials || []).forEach(function (c) { c.id = b64urlToBuf(c.id); });

      const cred = await navigator.credentials.create({ publicKey: options });
      await postJSON(urls.verifyUrl, {
        name: name,
        credential: {
          id: cred.id,
          rawId: bufToB64url(cred.rawId),
          type: cred.type,
          response: {
            clientDataJSON: bufToB64url(cred.response.clientDataJSON),
            attestationObject: bufToB64url(cred.response.attestationObject),
            transports: cred.response.getTransports ? cred.response.getTransports() : [],
          },
          clientExtensionResults: cred.getClientExtensionResults ? cred.getClientExtensionResults() : {},
          authenticatorAttachment: cred.authenticatorAttachment || null,
        },
      });
      showMessage("passkey-card-message", "Passkey added. You can now sign in with it.", false);
      setTimeout(function () { window.location.reload(); }, 900);
    } catch (err) {
      setBusy(button, false);
      showMessage("passkey-card-message", friendlyBrowserError(err), true);
    }
  }

  // ---------- rename / remove ----------

  async function renamePasskey(button) {
    const name = window.prompt("New name for this passkey:", button.dataset.currentName || "");
    if (name === null || !name.trim()) return;
    try {
      const result = await postJSON(button.dataset.url, { name: name });
      const label = document.getElementById("passkey-name-" + button.dataset.id);
      if (label) label.textContent = result.name;
      button.dataset.currentName = result.name;
      showMessage("passkey-card-message", "Passkey renamed.", false);
    } catch (err) {
      showMessage("passkey-card-message", friendlyBrowserError(err), true);
    }
  }

  async function removePasskey(button) {
    const ok = window.confirm(
      'Remove "' + (button.dataset.currentName || "this passkey") + '"? You won\'t be able to sign in with it anymore.'
    );
    if (!ok) return;
    try {
      await postJSON(button.dataset.url);
      const row = document.getElementById("passkey-row-" + button.dataset.id);
      if (row) row.remove();
      if (!document.querySelector("[id^='passkey-row-']")) {
        const empty = document.getElementById("passkey-empty");
        if (empty) empty.classList.remove("hidden");
      }
      showMessage("passkey-card-message", "Passkey removed.", false);
    } catch (err) {
      showMessage("passkey-card-message", friendlyBrowserError(err), true);
    }
  }

  // ---------- wiring ----------

  document.addEventListener("click", function (event) {
    const target = event.target.closest("[data-passkey-action]");
    if (!target) return;
    event.preventDefault();
    const action = target.dataset.passkeyAction;
    if (action === "login") signIn(target);
    else if (action === "add") addPasskey(target);
    else if (action === "rename") renamePasskey(target);
    else if (action === "remove") removePasskey(target);
  });
})();
