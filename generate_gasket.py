#!/usr/bin/env python3
"""
Stanley Growler Gasket Generator
Generates a 3MF file for 3D printing in TPU 95A.

Cross-section profile (U-channel gasket):

    outer wall          inner wall
     _______             _______
    |       |           |       |
    |       |           |       |
    |       |___________|       |
    |           channel         |
    |___________________________|
              base

Usage:
    python3 generate_gasket.py

    Adjust the parameters below to match your growler.
    The 3MF file will be created in the same directory.
"""

import math
import zipfile
import os
import sys

# ============================================================
# PARAMETERS - Adjust these to fit your Stanley Growler
# All dimensions in millimeters
# ============================================================

OD = 58.0           # Outer diameter of the gasket
ID = 40.0           # Inner diameter (center hole)
H_OUTER = 5.0       # Height of the outer wall (shorter, sits in lid groove)
H_INNER = 6.5       # Height of the inner wall (taller, seals against growler rim)
T_WALL = 2.0        # Wall thickness (both inner and outer)
T_BASE = 2.0        # Base/floor thickness
N_SEGMENTS = 120    # Circular resolution (higher = smoother)
OUTPUT_FILE = "stanley_growler_gasket.3mf"

# ============================================================


def generate_gasket(od, id_, h_outer, h_inner, t_wall, t_base, n_segments, output_file):
    r_outer = od / 2.0
    r_inner = id_ / 2.0

    if r_inner + t_wall >= r_outer - t_wall:
        print("Error: walls overlap. Increase OD, decrease ID, or reduce T_WALL.")
        sys.exit(1)
    if t_base >= min(h_outer, h_inner):
        print("Error: base is thicker than walls. Reduce T_BASE or increase wall heights.")
        sys.exit(1)

    print(f"Gasket dimensions:")
    print(f"  Outer diameter:    {od:.1f} mm")
    print(f"  Inner diameter:    {id_:.1f} mm")
    print(f"  Ring width:        {(od - id_) / 2:.1f} mm")
    print(f"  Outer wall height: {h_outer:.1f} mm")
    print(f"  Inner wall height: {h_inner:.1f} mm")
    print(f"  Wall thickness:    {t_wall:.1f} mm")
    print(f"  Base thickness:    {t_base:.1f} mm")
    print(f"  Channel depth:     {h_outer - t_base:.1f} mm")
    print(f"  Channel width:     {(od - id_) / 2 - 2 * t_wall:.1f} mm")

    profile = [
        (r_outer, 0.0),
        (r_outer, h_outer),
        (r_outer - t_wall, h_outer),
        (r_outer - t_wall, t_base),
        (r_inner + t_wall, t_base),
        (r_inner + t_wall, h_inner),
        (r_inner, h_inner),
        (r_inner, 0.0),
    ]

    n_profile = len(profile)

    vertices = []
    for i in range(n_segments):
        angle = 2.0 * math.pi * i / n_segments
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        for r, z in profile:
            vertices.append((r * cos_a, r * sin_a, z))

    triangles = []
    for i in range(n_segments):
        next_i = (i + 1) % n_segments
        for j in range(n_profile):
            next_j = (j + 1) % n_profile
            v0 = i * n_profile + j
            v1 = i * n_profile + next_j
            v2 = next_i * n_profile + next_j
            v3 = next_i * n_profile + j
            triangles.append((v0, v2, v1))
            triangles.append((v0, v3, v2))

    print(f"\nMesh: {len(vertices)} vertices, {len(triangles)} triangles")

    vert_xml = "\n".join(
        f'            <vertex x="{x:.6f}" y="{y:.6f}" z="{z:.6f}" />'
        for x, y, z in vertices
    )
    tri_xml = "\n".join(
        f'            <triangle v1="{a}" v2="{b}" v3="{c}" />'
        for a, b, c in triangles
    )

    model_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<model unit="millimeter" xml:lang="en-US"
       xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">
  <metadata name="Title">Stanley Growler Gasket</metadata>
  <metadata name="Description">Replacement gasket for Stanley Growler lid - TPU 95A</metadata>
  <resources>
    <object id="1" type="model" name="Stanley_Growler_Gasket">
      <mesh>
        <vertices>
{vert_xml}
        </vertices>
        <triangles>
{tri_xml}
        </triangles>
      </mesh>
    </object>
  </resources>
  <build>
    <item objectid="1" />
  </build>
</model>'''

    content_types = '''<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml" />
  <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml" />
</Types>'''

    rels = '''<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel" />
</Relationships>'''

    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(script_dir, output_file)

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("3D/3dmodel.model", model_xml)

    size = os.path.getsize(output_path)
    print(f"\nCreated: {output_path} ({size} bytes)")


if __name__ == "__main__":
    generate_gasket(OD, ID, H_OUTER, H_INNER, T_WALL, T_BASE, N_SEGMENTS, OUTPUT_FILE)
