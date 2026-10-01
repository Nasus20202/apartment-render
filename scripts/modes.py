"""Day / evening lighting switch, shared by build_interior.py and render.py.

Lamps are point/spot lights tagged role='lamp' with their 'power_on' wattage. Glowing materials (LEDs, bulbs)
are listed in EMISSIVE. Daylight is the world HDRI plus the 'Sun' lamp.
"""

import bpy

EMISSIVE = {"LED_Warm": 8.0, "Bulb_Warm": 20.0}


def set_mode(mode, lamps=None):
    """mode: 'day' or 'evening'. lamps: force the lamps on (True) or off (False); by default they are
    on only in the evening. Windowless rooms (bathroom, hall) are shot by day with lamps on."""
    evening = mode == "evening"
    lamps_on = evening if lamps is None else lamps
    for obj in bpy.data.objects:
        if obj.type == "LIGHT" and obj.get("role") == "lamp":
            obj.data.energy = obj["power_on"] if lamps_on else 0.0
            obj.hide_render = not lamps_on
    for name, strength in EMISSIVE.items():
        m = bpy.data.materials.get(name)
        if m:
            em = next(n for n in m.node_tree.nodes if n.bl_idname == "ShaderNodeEmission")
            em.inputs["Strength"].default_value = strength if lamps_on else 0.0
    sun = bpy.data.objects.get("Sun")
    if sun:
        sun.hide_render = evening
    world = bpy.context.scene.world
    if world and "World_Strength" in world.node_tree.nodes:
        # Evening: a dim blue-hour sky outside the windows
        world.node_tree.nodes["World_Strength"].outputs[0].default_value = 0.04 if evening else 1.0
    bpy.context.scene["lighting_mode"] = mode
