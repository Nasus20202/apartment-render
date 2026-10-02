"""Day / evening lighting switch, shared by build_interior.py and render.py.

Lamps are point/spot lights tagged role='lamp' with their 'power_on' wattage. Glowing materials (LEDs, bulbs)
are listed in EMISSIVE. Daylight is the world HDRI plus the 'Sun' lamp.
"""

import bpy

DAY_SKY_FILL = 1.5  # extra skylight bounced into the rooms by day (the view outside is unchanged)
EMISSIVE = {"LED_Warm": 8.0, "Bulb_Warm": 20.0}


def set_mode(mode):
    """mode: 'day' (sun and sky only) or 'evening' (no sun, dim sky, lamps on)."""
    lamps_on = mode == "evening"
    evening = lamps_on
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
        world.node_tree.nodes["World_Fill"].outputs[0].default_value = (
            1.0 if evening else DAY_SKY_FILL
        )
    bpy.context.scene["lighting_mode"] = mode
