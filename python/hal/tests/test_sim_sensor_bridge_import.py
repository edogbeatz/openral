def test_import_without_ros() -> None:
    from openral_hal.sim_sensor_bridge import _THUMB_INTERVAL_NS, SimSensorBridge

    assert SimSensorBridge.__name__ == "SimSensorBridge"
    # Dashboard MJPEG wants camera-rate video, not a 1 Hz still.
    assert _THUMB_INTERVAL_NS == 40_000_000
