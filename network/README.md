# MQTT Broker Configuration

`mosquitto.conf` configures the Eclipse Mosquitto broker used only by the optional network and packet-capture harness. It enables MQTT over TLS on port 8883, disables anonymous access outside the test setup, and points the broker to disposable certificates generated under the ignored `artifacts/network_tls` folder.

The main SUMO evaluation can be verified without this harness. To reproduce the communication measurement, follow [`docs/network_harness.md`](../docs/network_harness.md); Docker Compose mounts this configuration into the pinned broker container.
