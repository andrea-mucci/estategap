import ws from "k6/ws";
import { check, sleep } from "k6";

export const options = {
  scenarios: {
    websocket_chat: {
      executor: "constant-vus",
      vus: 100,
      duration: "10m",
    },
  },
  thresholds: {
    ws_session_duration: ["p(95)<5000"],
    ws_msgs_sent: ["count>0"],
  },
};

const wsUrl = __ENV.WS_URL || "ws://localhost:9090/chat";

export default function () {
  const response = ws.connect(wsUrl, {}, (socket) => {
    socket.on("open", () => {
      for (let index = 0; index < 5; index += 1) {
        socket.send(
          JSON.stringify({
            type: "message",
            content: `load-test message ${__VU}-${__ITER}-${index}`,
          }),
        );
        sleep(12);
      }
      socket.close();
    });
  });

  check(response, {
    "chat upgraded to websocket": (res) => res && res.status === 101,
  });
}

