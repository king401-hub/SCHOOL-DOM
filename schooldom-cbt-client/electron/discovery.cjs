const dgram = require("dgram");

const DISCOVERY_PORT = 4786;
const DISCOVERY_QUERY = "SCHOOLDOM_CBT_DISCOVER";

function discoverAdminRooms(timeoutMs = 1800) {
  return new Promise((resolve) => {
    const socket = dgram.createSocket("udp4");
    const rooms = new Map();
    const done = () => {
      try {
        socket.close();
      } catch {
        // ignore close errors
      }
      resolve([...rooms.values()]);
    };

    socket.on("message", (message, remote) => {
      try {
        const payload = JSON.parse(String(message));
        if (payload.type !== "SCHOOLDOM_CBT_ADMIN") return;
        const url = payload.urls?.[0] || `http://${remote.address}:${payload.port || 4785}`;
        rooms.set(url, {
          ...payload,
          url,
          address: remote.address,
        });
      } catch {
        // ignore unrelated UDP packets
      }
    });

    socket.bind(() => {
      socket.setBroadcast(true);
      const query = Buffer.from(DISCOVERY_QUERY);
      socket.send(query, 0, query.length, DISCOVERY_PORT, "255.255.255.255");
    });

    setTimeout(done, timeoutMs);
  });
}

module.exports = {
  discoverAdminRooms,
};
