(() => {
  let socket = null;
  let reconnectTimer = null;
  let retries = 0;

  function notificationChanged() {
    window.dispatchEvent(new CustomEvent("fc:notifications-changed"));
  }

  function connect() {
    if (socket && socket.readyState !== WebSocket.CLOSED) return;

    const scheme = window.location.protocol === "https:" ? "wss:" : "ws:";
    const currentSocket = new WebSocket(`${scheme}//${window.location.host}/ws/notifications/`);
    socket = currentSocket;

    currentSocket.addEventListener("open", () => {
      retries = 0;
      notificationChanged();
    });

    currentSocket.addEventListener("message", (message) => {
      try {
        if (JSON.parse(message.data).type === "notifications.changed") {
          notificationChanged();
        }
      } catch (error) {
        console.error("Invalid notification WebSocket message.", error);
      }
    });

    currentSocket.addEventListener("close", (event) => {
      if (socket !== currentSocket) return;
      socket = null;
      if (event.code === 4401) return;
      if (reconnectTimer !== null) return;
      const delay = Math.min(1000 * (2 ** retries++), 30000);
      reconnectTimer = window.setTimeout(() => {
        reconnectTimer = null;
        connect();
      }, delay);
    });

    currentSocket.addEventListener("error", () => currentSocket.close());
  }

  window.fcUpdateNotificationBadges = (count) => {
    document.querySelectorAll("[data-notification-badge]").forEach((badge) => {
      const unread = Number(count) || 0;
      badge.textContent = unread > 99 ? "99+" : String(unread);
      badge.classList.toggle("hidden", unread === 0);
    });
  };

  window.addEventListener("online", connect);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible" && (!socket || socket.readyState > WebSocket.OPEN)) {
      if (reconnectTimer !== null) {
        window.clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      connect();
    }
  });

  connect();
})();
