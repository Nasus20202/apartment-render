"""Material library for the interior: PBR materials from ambientCG plus procedural ones.

Textured materials use box-projected object coordinates scaled in metres, so procedural meshes need no UVs.
Every object is built at real size with unit object scale, so a texture's tile size stays true everywhere.
"""

from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parent.parent
ACG = ROOT / "assets" / "ambientcg"


def _mix_rgb(nodes, blend="MIX"):
    """ShaderNodeMix in RGBA mode. Returns (node, A socket, B socket, Result socket); names are ambiguous."""
    mix = nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = blend
    a = next(s for s in mix.inputs if s.name == "A" and s.type == "RGBA")
    b = next(s for s in mix.inputs if s.name == "B" and s.type == "RGBA")
    r = next(s for s in mix.outputs if s.name == "Result" and s.type == "RGBA")
    return mix, a, b, r


def _new(name):
    m = bpy.data.materials.get(name)
    if m:
        bpy.data.materials.remove(m)
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    return m, m.node_tree.nodes, m.node_tree.links, m.node_tree.nodes["Principled BSDF"]


def _tex(nodes, links, path, vector, non_color=False, proj_blend=0.25):
    t = nodes.new("ShaderNodeTexImage")
    t.image = bpy.data.images.load(str(path), check_existing=True)
    if non_color:
        t.image.colorspace_settings.name = "Non-Color"
    t.projection = "BOX"
    t.projection_blend = proj_blend
    links.new(vector, t.inputs["Vector"])
    return t


def _mapping(nodes, links, tile_m, rotate_z=0.0, coords="Object"):
    tc = nodes.new("ShaderNodeTexCoord")
    mp = nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1 / tile_m, 1 / tile_m, 1 / tile_m)
    mp.inputs["Rotation"].default_value[2] = rotate_z
    links.new(tc.outputs[coords], mp.inputs["Vector"])
    return mp.outputs["Vector"]


def _maps(asset_id):
    d = ACG / asset_id
    found = {}
    for f in d.glob("*.jpg"):
        for key in (
            "Color",
            "Roughness",
            "NormalGL",
            "Displacement",
            "Opacity",
            "Metalness",
            "AmbientOcclusion",
        ):
            if f.stem.endswith("_" + key):
                found[key] = f
    if "Color" not in found:
        raise FileNotFoundError(
            f"{asset_id}: no Color map in {d}. Run scripts/fetch_assets.py first."
        )
    return found


def pbr(
    name,
    asset_id,
    tile_m=1.0,
    hue=0.5,
    sat=1.0,
    val=1.0,
    rough_mul=1.0,
    rough_add=0.0,
    normal_strength=1.0,
    sheen=0.0,
    rotate_z=0.0,
    coords="Object",
    tint=None,
    bump_disp=0.0,
):
    """ambientCG material. hue/sat/val adjust the colour map (0.5/1/1 = unchanged). tint multiplies RGB."""
    m, nodes, links, bsdf = _new(name)
    maps = _maps(asset_id)
    vec = _mapping(nodes, links, tile_m, rotate_z, coords)

    col = _tex(nodes, links, maps["Color"], vec)
    hsv = nodes.new("ShaderNodeHueSaturation")
    hsv.inputs["Hue"].default_value = hue
    hsv.inputs["Saturation"].default_value = sat
    hsv.inputs["Value"].default_value = val
    links.new(col.outputs["Color"], hsv.inputs["Color"])
    out = hsv.outputs["Color"]
    if tint:
        mix, a, b, r = _mix_rgb(nodes, "MULTIPLY")
        mix.inputs["Factor"].default_value = 1.0
        b.default_value = (*tint, 1)
        links.new(out, a)
        out = r
    links.new(out, bsdf.inputs["Base Color"])

    if "Roughness" in maps:
        r = _tex(nodes, links, maps["Roughness"], vec, non_color=True)
        ma = nodes.new("ShaderNodeMath")
        ma.operation = "MULTIPLY_ADD"
        ma.use_clamp = True
        ma.inputs[1].default_value = rough_mul
        ma.inputs[2].default_value = rough_add
        links.new(r.outputs["Color"], ma.inputs[0])
        links.new(ma.outputs[0], bsdf.inputs["Roughness"])
    if "NormalGL" in maps:
        n = _tex(nodes, links, maps["NormalGL"], vec, non_color=True)
        nm = nodes.new("ShaderNodeNormalMap")
        nm.inputs["Strength"].default_value = normal_strength
        links.new(n.outputs["Color"], nm.inputs["Color"])
        links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    if bump_disp and "Displacement" in maps:
        # Shading-only relief (no real displacement), for rugs and boucle
        d = _tex(nodes, links, maps["Displacement"], vec, non_color=True)
        b = nodes.new("ShaderNodeBump")
        b.inputs["Strength"].default_value = bump_disp
        links.new(d.outputs["Color"], b.inputs["Height"])
        if "NormalGL" in maps:
            links.new(nm.outputs["Normal"], b.inputs["Normal"])
        links.new(b.outputs["Normal"], bsdf.inputs["Normal"])
    if sheen:
        bsdf.inputs["Sheen Weight"].default_value = sheen
        bsdf.inputs["Sheen Roughness"].default_value = 0.5
    return m


def paint(name, rgb, roughness=0.85, relief=0.15, relief_tile=1.2):
    """Matte wall paint over a faint plaster relief taken from the Plaster001 normal map."""
    m, nodes, links, bsdf = _new(name)
    bsdf.inputs["Base Color"].default_value = (*rgb, 1)
    bsdf.inputs["Roughness"].default_value = roughness
    maps = _maps("Plaster001")
    vec = _mapping(nodes, links, relief_tile)
    n = _tex(nodes, links, maps["NormalGL"], vec, non_color=True)
    nm = nodes.new("ShaderNodeNormalMap")
    nm.inputs["Strength"].default_value = relief
    links.new(n.outputs["Color"], nm.inputs["Color"])
    links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    return m


def tiles(name, asset_id, tile_w, tile_h, grout_rgb=(0.62, 0.58, 0.53), grout_w=0.002, **kw):
    """Stone texture laid as rectangular tiles with grout lines (Brick Texture as the mask)."""
    m = pbr(name, asset_id, **kw)
    nodes, links = m.node_tree.nodes, m.node_tree.links
    bsdf = nodes["Principled BSDF"]
    tc = nodes.new("ShaderNodeTexCoord")
    sep = nodes.new("ShaderNodeSeparateXYZ")
    links.new(tc.outputs["Object"], sep.inputs["Vector"])
    # Walls are vertical: use (x+y, z) as the tile plane so a single setup serves floors and walls.
    # Floors use (x, y). The caller picks via kw 'plane'.
    brick = nodes.new("ShaderNodeTexBrick")
    brick.offset = 0.5
    brick.squash = 1.0
    brick.inputs["Scale"].default_value = 1.0
    brick.inputs["Mortar Size"].default_value = grout_w
    brick.inputs["Brick Width"].default_value = tile_w
    brick.inputs["Row Height"].default_value = tile_h
    brick.inputs["Mortar Smooth"].default_value = 0.2
    brick.inputs["Color1"].default_value = (1, 1, 1, 1)
    brick.inputs["Color2"].default_value = (1, 1, 1, 1)
    brick.inputs["Mortar"].default_value = (0, 0, 0, 1)
    comb = nodes.new("ShaderNodeCombineXYZ")
    add = nodes.new("ShaderNodeMath")
    add.operation = "ADD"
    links.new(sep.outputs["X"], add.inputs[0])
    links.new(sep.outputs["Y"], add.inputs[1])
    m["_tile_nodes"] = True
    # default: floor plane (x, y); walls are switched by set_tile_plane()
    links.new(sep.outputs["X"], comb.inputs["X"])
    links.new(sep.outputs["Y"], comb.inputs["Y"])
    links.new(comb.outputs["Vector"], brick.inputs["Vector"])
    base_col = bsdf.inputs["Base Color"].links[0].from_socket
    mix, mix_a, mix_b, mix_r = _mix_rgb(nodes)
    mix_b.default_value = (*grout_rgb, 1)
    links.new(brick.outputs["Fac"], mix.inputs["Factor"])  # Fac is 1 in the mortar
    links.new(base_col, mix_a)
    links.new(mix_r, bsdf.inputs["Base Color"])
    # Grout sits slightly recessed: bump from the mask
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.4
    bump.inputs["Distance"].default_value = 0.002
    bump.invert = True
    links.new(brick.outputs["Fac"], bump.inputs["Height"])
    prev = bsdf.inputs["Normal"].links[0].from_socket if bsdf.inputs["Normal"].links else None
    if prev:
        links.new(prev, bump.inputs["Normal"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return m


def tiles_wall(name, asset_id, tile_w, tile_h, along="x", **kw):
    """Wall variant of tiles(): the tile plane is (along-axis, z)."""
    m = tiles(name, asset_id, tile_w, tile_h, **kw)
    nodes, links = m.node_tree.nodes, m.node_tree.links
    sep = next(n for n in nodes if n.bl_idname == "ShaderNodeSeparateXYZ")
    comb = next(n for n in nodes if n.bl_idname == "ShaderNodeCombineXYZ")
    links.new(sep.outputs["X" if along == "x" else "Y"], comb.inputs["X"])
    links.new(sep.outputs["Z"], comb.inputs["Y"])
    return m


def hex_tiles(name, radius, colors, grout_rgb, plane="xz", grout_w=0.003, rough=0.12):
    """Glazed hexagon tiles (pointy-top, `radius` = centre to corner in metres) from a generated mask.

    The image covers 6 x 4 lattice periods so the per-tile tone variation doesn't visibly repeat. R holds
    the tile mask (0 in the grout), G a random value per tile. `plane` is the object-space plane the tiles
    lie in: "xz" / "yz" for walls, "xy" for floors."""
    import numpy as np

    a = 3**0.5 * radius
    nx, ny = 6, 4
    wm, hm = nx * a, ny * 3 * radius
    w = 2048
    h = round(w * hm / wm)
    px = wm / w
    xs = (np.arange(w) + 0.5) * px
    ys = (np.arange(h) + 0.5) * px
    x, y = np.meshgrid(xs, ys)
    rng = np.random.default_rng(7)
    tone = rng.random((2, ny, nx))
    # Lattice A: centres at (i a, j 3R); lattice B (the offset rows): ((i + .5) a, (j + .5) 3R). The two
    # nearest of the 3 x 3 neighbours on each lattice give the owning tile and its nearest neighbour.
    d1 = np.full(x.shape, np.inf, dtype=np.float32)
    d2 = d1.copy()
    var = np.zeros(x.shape, dtype=np.float32)
    for lat, off in ((0, 0.0), (1, 0.5)):
        i0 = np.rint(x / a - off)
        j0 = np.rint(y / (3 * radius) - off)
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                i, j = i0 + di, j0 + dj
                d = ((x - (i + off) * a) ** 2 + (y - (j + off) * 3 * radius) ** 2).astype(
                    np.float32
                )
                v = tone[lat, j.astype(int) % ny, i.astype(int) % nx]
                closer = d < d1
                d2 = np.where(closer, d1, np.minimum(d2, d))
                var = np.where(closer, v, var)
                d1 = np.where(closer, d, d1)
    t = (d2 - d1) / (2 * a)  # distance to the tile edge
    mask = np.clip((t - grout_w / 2) / px + 0.5, 0, 1)
    img = np.zeros((h, w, 4), dtype=np.float32)
    img[..., 0], img[..., 1], img[..., 3] = mask, var, 1.0
    im = bpy.data.images.get(name + "_mask") or bpy.data.images.new(name + "_mask", w, h)
    im.colorspace_settings.name = "Non-Color"
    im.pixels.foreach_set(img[::-1].ravel())  # image rows run bottom-up
    im.pack()

    m, nodes, links, bsdf = _new(name)
    tc = nodes.new("ShaderNodeTexCoord")
    sep = nodes.new("ShaderNodeSeparateXYZ")
    comb = nodes.new("ShaderNodeCombineXYZ")
    mp = nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1 / wm, 1 / hm, 1)
    links.new(tc.outputs["Object"], sep.inputs["Vector"])
    links.new(sep.outputs[plane[0].upper()], comb.inputs["X"])
    links.new(sep.outputs[plane[1].upper()], comb.inputs["Y"])
    links.new(comb.outputs["Vector"], mp.inputs["Vector"])
    t_node = nodes.new("ShaderNodeTexImage")
    t_node.image = im
    t_node.extension = "REPEAT"
    t_node.interpolation = "Linear"
    links.new(mp.outputs["Vector"], t_node.inputs["Vector"])
    sp = nodes.new("ShaderNodeSeparateColor")
    links.new(t_node.outputs["Color"], sp.inputs["Color"])
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*colors[0], 1)
    ramp.color_ramp.elements[1].color = (*colors[1], 1)
    links.new(sp.outputs["Green"], ramp.inputs["Fac"])
    mix, ma, mb, mr = _mix_rgb(nodes)
    mb.default_value = (*grout_rgb, 1)
    inv = nodes.new("ShaderNodeMath")
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    links.new(sp.outputs["Red"], inv.inputs[1])
    links.new(inv.outputs[0], mix.inputs["Factor"])
    links.new(ramp.outputs["Color"], ma)
    links.new(mr, bsdf.inputs["Base Color"])
    rmix = nodes.new("ShaderNodeMath")
    rmix.operation = "MULTIPLY_ADD"
    rmix.inputs[1].default_value = 0.8 - rough
    rmix.inputs[2].default_value = rough
    links.new(inv.outputs[0], rmix.inputs[0])
    links.new(rmix.outputs[0], bsdf.inputs["Roughness"])
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.6
    bump.inputs["Distance"].default_value = 0.0015
    links.new(sp.outputs["Red"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    bsdf.inputs["Coat Weight"].default_value = 0.3
    return m


def principled(
    name,
    rgb,
    roughness=0.5,
    metallic=0.0,
    coat=0.0,
    sheen=0.0,
    transmission=0.0,
    ior=1.45,
    alpha=1.0,
    emission=None,
    emission_strength=0.0,
    subsurface=0.0,
):
    m, nodes, links, bsdf = _new(name)
    bsdf.inputs["Base Color"].default_value = (*rgb, 1)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Coat Weight"].default_value = coat
    bsdf.inputs["Sheen Weight"].default_value = sheen
    bsdf.inputs["Transmission Weight"].default_value = transmission
    bsdf.inputs["IOR"].default_value = ior
    bsdf.inputs["Alpha"].default_value = alpha
    bsdf.inputs["Subsurface Weight"].default_value = subsurface
    if emission:
        bsdf.inputs["Emission Color"].default_value = (*emission, 1)
        bsdf.inputs["Emission Strength"].default_value = emission_strength
    m.diffuse_color = (*rgb, 1)
    return m


def glass(name="Glass_Clear", tint=(0.96, 0.98, 0.97)):
    """Architectural glass: thin, so make it fully transmissive with no refraction offset."""
    m, nodes, links, bsdf = _new(name)
    bsdf.inputs["Base Color"].default_value = (*tint, 1)
    bsdf.inputs["Roughness"].default_value = 0.0
    bsdf.inputs["Transmission Weight"].default_value = 1.0
    bsdf.inputs["IOR"].default_value = 1.52
    # Shadow rays pass straight through panes so daylight isn't blocked (no caustics in Cycles anyway)
    lp = nodes.new("ShaderNodeLightPath")
    tr = nodes.new("ShaderNodeBsdfTransparent")
    tr.inputs["Color"].default_value = (*tint, 1)
    mix = nodes.new("ShaderNodeMixShader")
    out = nodes["Material Output"]
    links.new(lp.outputs["Is Shadow Ray"], mix.inputs["Fac"])
    links.new(bsdf.outputs["BSDF"], mix.inputs[1])
    links.new(tr.outputs["BSDF"], mix.inputs[2])
    links.new(mix.outputs["Shader"], out.inputs["Surface"])
    m.diffuse_color = (*tint, 0.25)
    return m


def paper(name="Paper_Shade", rgb=(0.95, 0.92, 0.85)):
    """Rice-paper lamp shade: diffuse plus translucency, so it glows when lit from inside."""
    m, nodes, links, bsdf = _new(name)
    bsdf.inputs["Base Color"].default_value = (*rgb, 1)
    bsdf.inputs["Roughness"].default_value = 0.9
    tl = nodes.new("ShaderNodeBsdfTranslucent")
    tl.inputs["Color"].default_value = (*rgb, 1)
    mix = nodes.new("ShaderNodeMixShader")
    mix.inputs["Fac"].default_value = 0.55
    links.new(bsdf.outputs["BSDF"], mix.inputs[1])
    links.new(tl.outputs["BSDF"], mix.inputs[2])
    links.new(mix.outputs["Shader"], nodes["Material Output"].inputs["Surface"])
    m.diffuse_color = (*rgb, 1)
    return m


def sheer(name, asset_id="Fabric036", rgb=(0.93, 0.91, 0.86)):
    """Sheer linen curtain: partly transparent and translucent, with the fabric weave in the normal."""
    m = pbr(name, asset_id, tile_m=0.35, sat=0.2, val=1.6, sheen=0.4, tint=rgb)
    nodes, links = m.node_tree.nodes, m.node_tree.links
    bsdf = nodes["Principled BSDF"]
    tl = nodes.new("ShaderNodeBsdfTranslucent")
    tl.inputs["Color"].default_value = (*rgb, 1)
    tr = nodes.new("ShaderNodeBsdfTransparent")
    m1 = nodes.new("ShaderNodeMixShader")
    m1.inputs["Fac"].default_value = 0.45
    links.new(bsdf.outputs["BSDF"], m1.inputs[1])
    links.new(tl.outputs["BSDF"], m1.inputs[2])
    m2 = nodes.new("ShaderNodeMixShader")
    m2.inputs["Fac"].default_value = 0.35
    links.new(m1.outputs["Shader"], m2.inputs[1])
    links.new(tr.outputs["BSDF"], m2.inputs[2])
    links.new(m2.outputs["Shader"], nodes["Material Output"].inputs["Surface"])
    return m


def emission(name, rgb=(1.0, 0.85, 0.65), strength=5.0):
    m, nodes, links, bsdf = _new(name)
    em = nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*rgb, 1)
    em.inputs["Strength"].default_value = strength
    links.new(em.outputs["Emission"], nodes["Material Output"].inputs["Surface"])
    return m


def library():
    """Build every shared material once; returns a dict name -> material."""
    L = {}
    # Architecture
    L["wall"] = paint("Wall_WarmWhite", (0.86, 0.84, 0.80))
    L["wall_accent"] = paint("Wall_Greige", (0.62, 0.58, 0.52))
    L["ceiling"] = paint("Ceiling_White", (0.90, 0.90, 0.88), relief=0.05)
    L["floor_oak"] = pbr(
        "Floor_Oak", "WoodFloor062", tile_m=1.6, sat=0.45, val=1.75, rough_add=0.05
    )
    # Bathroom: terrazzo floor tiles; handmade-look glossy subway tiles on the walls (15 x 10 cm, the
    # texture holds 4 x 6 of them), white everywhere and forest green on the shower's back wall
    L["bath_floor"] = tiles(
        "Bath_Floor_Grey",
        "Plaster001",
        0.60,
        0.60,
        grout_rgb=(0.06, 0.06, 0.06),
        grout_w=0.003,
        tile_m=1.2,
        sat=0.0,
        val=0.3,
        rough_add=0.25,
        normal_strength=0.3,
    )
    # Large-format white wall tiles (60 x 30 cm, glossy) with forest-green hexagons in the shower
    for ax in "xy":
        L[f"bath_wall_{ax}"] = tiles_wall(
            f"Bath_WhiteTile_{ax}",
            "Plaster001",
            0.60,
            0.30,
            along=ax,
            grout_rgb=(0.34, 0.34, 0.32),
            grout_w=0.002,
            tile_m=1.2,
            sat=0.0,
            val=0.9,
            rough_mul=0.0,
            rough_add=0.12,
            normal_strength=0.2,
        )
    L["hex_green"] = hex_tiles(
        "Hex_Forest", 0.05, ((0.015, 0.06, 0.04), (0.035, 0.105, 0.07)), (0.04, 0.045, 0.04), "xz"
    )
    L["hex_floor"] = hex_tiles(
        "Hex_Graphite", 0.05, ((0.10, 0.105, 0.105), (0.17, 0.175, 0.175)), (0.06, 0.06, 0.06), "xy"
    )
    L["sill_stone"] = pbr("Sill_Terrazzo", "Terrazzo013", tile_m=0.5, sat=0.6, rough_add=0.1)
    L["pvc"] = principled("PVC_White", (0.88, 0.88, 0.87), roughness=0.35)
    L["glass"] = glass()
    L["skirting"] = principled("Skirting_White", (0.85, 0.84, 0.81), roughness=0.4)
    L["door_white"] = principled("Door_WhiteMatte", (0.84, 0.83, 0.80), roughness=0.45)
    L["door_entrance"] = principled("Door_Entrance_Graphite", (0.08, 0.08, 0.08), roughness=0.5)
    L["radiator"] = principled("Radiator_White", (0.86, 0.86, 0.85), roughness=0.3)
    L["balcony"] = principled("Balcony_Concrete", (0.45, 0.44, 0.42), roughness=0.85)
    L["balcony_deck"] = pbr("Balcony_Deck", "Wood094", tile_m=1.0, sat=0.6, val=0.7, rough_add=0.2)
    # Furniture
    L["oak"] = pbr("Oak_Veneer", "Wood094", tile_m=1.2, sat=0.75, val=1.1, rough_add=0.1)
    L["oak_rich"] = pbr(
        "Oak_Rich",
        "WoodFloor062",
        tile_m=0.9,
        sat=0.95,
        val=0.9,
        rough_add=0.05,
        normal_strength=2.5,
        tint=(0.78, 0.60, 0.42),
    )
    L["oak_dark"] = pbr("Oak_Smoked", "Wood094", tile_m=1.2, sat=0.6, val=0.45, rough_add=0.1)
    L["front_greige"] = principled("Front_Greige_Matte", (0.55, 0.52, 0.47), roughness=0.55)
    L["front_white"] = principled("Front_White_Matte", (0.83, 0.82, 0.79), roughness=0.5)
    L["worktop"] = pbr("Worktop_Marble", "Marble012", tile_m=1.5, sat=0.5, rough_add=0.2)
    L["sofa_fabric"] = pbr(
        "Sofa_Oatmeal",
        "Fabric062",
        tile_m=0.25,
        sat=0.6,
        val=1.0,
        sheen=0.6,
        tint=(0.85, 0.80, 0.72),
    )
    L["boucle"] = pbr(
        "Boucle_Cream", "Carpet016", tile_m=0.3, sat=0.6, val=0.95, sheen=0.8, bump_disp=0.4
    )
    L["rug"] = pbr("Rug_Wool", "Carpet016", tile_m=0.5, sat=0.6, val=1.05, sheen=0.5, bump_disp=0.6)
    L["cotton_white"] = pbr("Cotton_White", "Fabric019", tile_m=0.3, sat=0.0, val=1.1, sheen=0.5)
    L["linen"] = pbr(
        "Linen_Natural",
        "Fabric036",
        tile_m=0.25,
        sat=0.4,
        val=1.2,
        sheen=0.5,
        tint=(0.92, 0.88, 0.80),
    )
    # Dark forest green accents: velvet and linen tinted from neutral weaves, and a matte paint for niche backs
    L["velvet_green"] = pbr(
        "Velvet_Forest",
        "Fabric062",
        tile_m=0.25,
        sat=0.0,
        val=1.0,
        sheen=0.9,
        tint=(0.07, 0.16, 0.10),
    )
    L["linen_green"] = pbr(
        "Linen_Forest",
        "Fabric036",
        tile_m=0.25,
        sat=0.0,
        val=1.0,
        sheen=0.5,
        tint=(0.09, 0.18, 0.12),
    )
    L["paint_green"] = paint("Paint_ForestGreen", (0.075, 0.15, 0.10), roughness=0.8, relief=0.08)
    L["paper_mount"] = principled("Paper_Mount", (0.86, 0.84, 0.79), roughness=0.9)
    # Office chair: charcoal upholstery and a black mesh back
    L["fabric_charcoal"] = pbr(
        "Fabric_Charcoal",
        "Fabric062",
        tile_m=0.2,
        sat=0.0,
        val=1.0,
        sheen=0.3,
        tint=(0.05, 0.05, 0.055),
    )
    L["mesh_black"] = pbr(
        "Mesh_Black",
        "Fabric036",
        tile_m=0.08,
        sat=0.0,
        val=1.0,
        tint=(0.02, 0.02, 0.022),
        normal_strength=2.0,
    )
    L["linen_sage"] = pbr("Linen_Sage", "Fabric066", tile_m=0.25, sat=1.1, val=1.25, sheen=0.5)
    # Exterior: balcony railing, facade, courtyard
    L["glass_railing"] = glass("Glass_Railing", tint=(0.86, 0.93, 0.91))
    L["graphite"] = principled("Metal_Graphite", (0.06, 0.065, 0.07), roughness=0.4, metallic=1.0)
    L["facade"] = paint("Facade_Plaster", (0.80, 0.79, 0.76), relief=0.25)
    L["facade_far"] = paint("Facade_Greige", (0.60, 0.58, 0.54), relief=0.3)
    L["grass"] = pbr("Lawn", "Grass004", tile_m=2.0, sat=0.85, val=0.85)
    L["paving"] = pbr("Paving_Concrete", "PavingStones070", tile_m=2.5, sat=0.5)
    L["sheer"] = sheer("Curtain_Sheer")
    L["paper"] = paper()
    L["black_metal"] = principled(
        "Metal_BlackMatte", (0.03, 0.03, 0.03), roughness=0.45, metallic=1.0
    )
    L["steel"] = principled("Steel_Brushed", (0.6, 0.6, 0.6), roughness=0.3, metallic=1.0)
    L["chrome"] = principled("Chrome", (0.9, 0.9, 0.9), roughness=0.05, metallic=1.0)
    L["ceramic"] = principled("Ceramic_White", (0.88, 0.88, 0.86), roughness=0.08, coat=0.5)
    L["stone_resin"] = principled("StoneResin_White", (0.84, 0.83, 0.80), roughness=0.6)
    L["black_glass"] = principled("BlackGlass", (0.005, 0.005, 0.005), roughness=0.03, coat=1.0)
    L["screen_off"] = principled("Screen_Off", (0.002, 0.002, 0.002), roughness=0.08, coat=1.0)
    L["plastic_white"] = principled("Plastic_White", (0.85, 0.85, 0.84), roughness=0.35)
    L["plastic_black"] = principled("Plastic_Black", (0.02, 0.02, 0.02), roughness=0.4)
    L["mirror"] = principled("Mirror", (0.95, 0.95, 0.95), roughness=0.0, metallic=1.0)
    L["mirror_smoked"] = principled(
        "Mirror_Smoked", (0.72, 0.69, 0.66), roughness=0.02, metallic=1.0
    )
    L["led"] = emission("LED_Warm", (1.0, 0.82, 0.62), 8.0)
    L["bulb"] = emission("Bulb_Warm", (1.0, 0.78, 0.55), 20.0)
    L["towel"] = pbr("Towel_Oat", "Carpet016", tile_m=0.15, sat=0.4, val=1.2, sheen=0.7)
    L["mattress"] = pbr("Mattress_White", "Fabric019", tile_m=0.2, sat=0.0, val=1.0, sheen=0.3)
    return L
