#!/usr/bin/env bash
# 15 s in-place trot on cricket through /openral/candidate_action, then Hub stand.
set -euo pipefail
SSH_CONFIG="${BREV_SSH_CONFIG:-$HOME/.brev/ssh_config}"
HOST="${GO2_BREV_HOST:-abundant-turquoise-cricket}"
CONTAINER="${GO2_CONTAINER:-openral-jazzy-go2}"

ssh -T -F "$SSH_CONFIG" -o StrictHostKeyChecking=no -o ConnectTimeout=20 "$HOST" \
  "docker exec -i $CONTAINER bash -s" <<'REMOTE'
set +u
source /opt/ros/jazzy/setup.bash
source /openral/install/setup.bash
export ROS_DOMAIN_ID=77
python3 - <<'PY'
import math, time
import rclpy
from rclpy.qos import QoSDurabilityPolicy, QoSHistoryPolicy, QoSProfile, QoSReliabilityPolicy
from sensor_msgs.msg import JointState
from openral_msgs.msg import ActionChunk

HOME = [-0.1, 0.9, -1.8, 0.1, 0.9, -1.8, -0.1, 0.9, -1.8, 0.1, 0.9, -1.8]

def pose(t: float) -> list[float]:
    s = math.sin(2.0 * math.pi * 0.7 * t)
    lift_a = 0.45 * max(s, 0.0)
    lift_b = 0.45 * max(-s, 0.0)
    hip = 0.18 * s
    q = list(HOME)
    q[0] = -0.1 + hip
    q[1] = 0.9 + lift_a
    q[3] = 0.1 + hip
    q[4] = 0.9 + lift_b
    q[6] = -0.1 - hip
    q[7] = 0.9 + lift_b
    q[9] = 0.1 - hip
    q[10] = 0.9 + lift_a
    return q

rclpy.init()
node = rclpy.create_node("go2_march")
qos = QoSProfile(
    history=QoSHistoryPolicy.KEEP_LAST,
    depth=10,
    reliability=QoSReliabilityPolicy.RELIABLE,
    durability=QoSDurabilityPolicy.VOLATILE,
)
pub = node.create_publisher(ActionChunk, "/openral/candidate_action", qos)
# Readback: a published chunk proves nothing — the kernel or HAL can drop it
# and leave the dog in Hub stand. Range over FL_thigh is the ground truth.
seen: list[float] = []
node.create_subscription(JointState, "/joint_states", lambda m: seen.append(m.position[1]), 10)
deadline = time.monotonic() + 4.0
while time.monotonic() < deadline and pub.get_subscription_count() == 0:
    rclpy.spin_once(node, timeout_sec=0.05)
print(f"WATCH_NOW candidate_subs={pub.get_subscription_count()} duration=15s", flush=True)

def send(targets, i: int) -> None:
    chunk = ActionChunk()
    chunk.header.stamp = node.get_clock().now().to_msg()
    chunk.control_mode = 0
    chunk.horizon = 1
    chunk.n_dof = 12
    chunk.flat = [float(x) for x in targets]
    chunk.rskill_id = "openral/go2-march-test"
    chunk.trace_id = f"go2-march-{i}"
    pub.publish(chunk)
    rclpy.spin_once(node, timeout_sec=0.01)

hz, duration = 20.0, 15.0
n = int(duration * hz)
t0 = time.monotonic()
for i in range(n):
    send(pose(time.monotonic() - t0), i)
    time.sleep(1.0 / hz)
for i in range(12):
    send(HOME, 10_000 + i)
    time.sleep(0.05)
span = (max(seen) - min(seen)) if seen else 0.0
print(f"march_done FL_thigh_span={span:.3f} rad samples={len(seen)}", flush=True)
if span < 0.05:
    print("WARNING: dog did not move — check kernel latch / HAL active", flush=True)
node.destroy_node()
rclpy.shutdown()
PY
REMOTE
