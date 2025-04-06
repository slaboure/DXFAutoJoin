#!/usr/bin/env python3
# ------------------------------------------------------------------------------
# Copyright (C) 2025 Sacha Labourey
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
# ------------------------------------------------------------------------------

import math
import ezdxf
from ezdxf.math import Vec2
import re

def distance_2d(p1, p2):
    """Euclidean distance in 2D."""
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])

def angle_of_point(center, pt):
    """
    Return angle in degrees [0..360) from center->pt, CCW from +X axis.
    """
    dx = pt[0] - center[0]
    dy = pt[1] - center[1]
    return math.degrees(math.atan2(dy, dx)) % 360

def normalize_arc_angles(start_angle, end_angle):
    """
    Make sure arcs are CCW in [0..360 or 0..720).
    If end_angle < start_angle, add 360 so it's a positive sweep.
    Returns (start_angle, end_angle, sweep).
    """
    s = start_angle % 360
    e = end_angle % 360
    sweep = e - s
    if sweep < 0:
        e += 360
        sweep = e - s
    return s, e, sweep

def point_on_arc(center, radius, angle_deg):
    """Return (x,y) on the circle for given center+radius+angle."""
    a = math.radians(angle_deg)
    return (center[0] + radius * math.cos(a),
            center[1] + radius * math.sin(a))

def extract_entities(msp):
    """
    Return a list of entities with a uniform data structure:
      {
        'type': 'LINE' or 'ARC',
        'start': (x1, y1),
        'end':   (x2, y2),
        'handle': 'entity_handle',  # Unique Handle ID
        -- for arcs only:
        'center': (cx, cy),
        'radius': r,
        'start_angle': sa,
        'end_angle': ea,
      }
    """
    result = []

    # Lines
    for ln in msp.query("LINE"):
        start = (ln.dxf.start.x, ln.dxf.start.y)
        end   = (ln.dxf.end.x,   ln.dxf.end.y)
        result.append({
            "type": "LINE",
            "start": start,
            "end": end,
            "handle": ln.dxf.handle,  # Track Handle ID
        })

    # Arcs
    for arc in msp.query("ARC"):
        center = (arc.dxf.center.x, arc.dxf.center.y)
        radius = arc.dxf.radius
        sa_deg = arc.dxf.start_angle
        ea_deg = arc.dxf.end_angle
        # Arc endpoints
        arc_start = point_on_arc(center, radius, sa_deg)
        arc_end   = point_on_arc(center, radius, ea_deg)
        # Normalize angles CCW
        sa_norm, ea_norm, _ = normalize_arc_angles(sa_deg, ea_deg)

        result.append({
            "type": "ARC",
            "center": center,
            "radius": radius,
            "start_angle": sa_norm,
            "end_angle": ea_norm,
            "start": arc_start,
            "end": arc_end,
            "handle": arc.dxf.handle,  # Track Handle ID
        })

    return result

def unify_endpoints(entities, tolerance=1e-3):
    """
    1) Gather endpoints (start+end).
    2) Merge points within 'tolerance'.
    3) Update entity endpoints.
    4) For arcs, recalc angles if needed.
    """
    # Gather all endpoints
    all_pts = []
    for e in entities:
        all_pts.append(e["start"])
        all_pts.append(e["end"])

    # Merge
    merged = []
    point_map = {}
    for p in all_pts:
        found = False
        for mp in merged:
            if distance_2d(p, mp) <= tolerance:
                point_map[p] = mp
                found = True
                break
        if not found:
            merged.append(p)
            point_map[p] = p

    # Update
    for e in entities:
        s_new = point_map[e["start"]]
        e_new = point_map[e["end"]]
        e["start"] = s_new
        e["end"]   = e_new

        if e["type"] == "ARC":
            c = e["center"]
            # new radius as average distance
            r1 = distance_2d(c, s_new)
            r2 = distance_2d(c, e_new)
            r_avg = 0.5*(r1 + r2)
            e["radius"] = r_avg

            sa = angle_of_point(c, s_new)
            ea = angle_of_point(c, e_new)
            sa, ea, _ = normalize_arc_angles(sa, ea)
            e["start_angle"] = sa
            e["end_angle"]   = ea

    return entities

def build_adjacency(entities):
    """
    Each entity is an 'edge' from e["start"] to e["end"].
    We'll build adjacency so we can find connected sets.
    
    adjacency[node] = list of entity indices that start/end at 'node'.
    """
    adjacency = {}
    def add_node(p, ent_idx):
        if p not in adjacency:
            adjacency[p] = []
        adjacency[p].append(ent_idx)

    for i, e in enumerate(entities):
        add_node(e["start"], i)
        add_node(e["end"],   i)

    return adjacency

def find_connected_groups(entities):
    """
    Return a list of groups, each group is a set of entity indices
    that connect to each other via shared endpoints.
    """
    adjacency = build_adjacency(entities)
    visited = set()
    groups = []

    # We do an entity-based BFS/DFS for each unvisited entity.
    ent_adjacency = {i: set() for i in range(len(entities))}

    # Build adjacency of entities: any that share a node are connected
    for node, ent_list in adjacency.items():
        # All entities in 'ent_list' share this node, so they're connected
        for e1 in ent_list:
            for e2 in ent_list:
                if e1 != e2:
                    ent_adjacency[e1].add(e2)

    def bfs(start_ent):
        queue = [start_ent]
        connected = {start_ent}
        while queue:
            cur = queue.pop(0)
            for neigh in ent_adjacency[cur]:
                if neigh not in connected:
                    connected.add(neigh)
                    queue.append(neigh)
        return connected

    for ent_idx in range(len(entities)):
        if ent_idx not in visited:
            group = bfs(ent_idx)
            groups.append(group)
            visited |= group

    return groups

# ------------------------------------------------------------------------------
# BELOW: Logic to "pre-join" lines into polylines
# ------------------------------------------------------------------------------

def build_line_adjacency(lines):
    """
    lines is a list of indices or dictionaries that represent line segments.
    We'll build adjacency on endpoints to find chain(s).
    adjacency[node] = list of line indices that start or end at node
    """
    adjacency = {}
    def add_node(p, line_idx):
        if p not in adjacency:
            adjacency[p] = []
        adjacency[p].append(line_idx)

    for i, ln in enumerate(lines):
        s = ln["start"]
        e = ln["end"]
        add_node(s, i)
        add_node(e, i)
    return adjacency

def chain_lines(lines):
    """
    lines: a list of dicts { 'type':'LINE', 'start':(x,y), 'end':(x,y) }
    Return a list of polylines, each polyline is a list of vertices (x, y).
    We find all possible "chains" of lines in the set. If there's branching, we
    produce multiple polylines.

    - We'll do a BFS/DFS approach, but each 'edge' (line) can only be used once.
    - For each line in the set, if not visited, start a chain from that line.
      We then walk forward as far as we can (matching end->start) and also backward
      if it can keep going from start->some other line's end, etc.
    """
    if not lines:
        return []

    adjacency = build_line_adjacency(lines)
    visited = set()  # set of line indices already in a chain
    polylines = []

    # Helper to get the "other" endpoint
    def other_end(line, pt):
        # line has start, end
        # if pt == line['start'] => other = line['end']
        # if pt == line['end']   => other = line['start']
        if distance_2d(pt, line["start"]) < 1e-12:
            return line["end"]
        else:
            return line["start"]

    for i, ln in enumerate(lines):
        if i in visited:
            continue
        # Start a chain from this line
        chain = []
        visited.add(i)

        # We'll treat ln's direction as start->end
        chain_pts = [ln["start"], ln["end"]]

        # Walk forward from ln["end"]
        forward_current = ln["end"]
        while True:
            # all lines connected at forward_current
            candidates = adjacency.get(forward_current, [])
            found_next = False
            for nxt_idx in candidates:
                if nxt_idx not in visited:
                    # check the other endpoint
                    nxt_line = lines[nxt_idx]
                    # if forward_current is nxt_line["start"], next is nxt_line["end"]
                    # or vice versa
                    # We'll unify them in the chain
                    visited.add(nxt_idx)
                    nxt_other = other_end(nxt_line, forward_current)
                    chain_pts.append(nxt_other)
                    forward_current = nxt_other
                    found_next = True
                    break
            if not found_next:
                break

        # Walk backward from ln["start"]
        backward_current = ln["start"]
        # We'll do it in *front* of chain_pts
        prefix = []
        while True:
            candidates = adjacency.get(backward_current, [])
            found_prev = False
            for nxt_idx in candidates:
                if nxt_idx not in visited:
                    visited.add(nxt_idx)
                    nxt_line = lines[nxt_idx]
                    nxt_other = other_end(nxt_line, backward_current)
                    # Insert at front of prefix
                    prefix.insert(0, nxt_other)
                    backward_current = nxt_other
                    found_prev = True
                    break
            if not found_prev:
                break

        # Now final chain of points is prefix + chain_pts
        final_pts = prefix + chain_pts
        polylines.append(final_pts)

    return polylines

def approximate_arc(arc, num_segments=20):
    """
    Approximate an arc as a series of line segments.
    """
    center = arc["center"]
    radius = arc["radius"]
    start_angle = arc["start_angle"]
    end_angle = arc["end_angle"]

    # Generate points along the arc
    points = []
    for i in range(num_segments + 1):
        angle = start_angle + i * (end_angle - start_angle) / num_segments
        points.append(point_on_arc(center, radius, angle))

    # Convert points to line segments
    segments = []
    for i in range(len(points) - 1):
        segments.append({"start": points[i], "end": points[i + 1], "handle": arc["handle"]})
    return segments

def is_point_in_polygon(point, polygon):
    """
    Use the ray-casting algorithm to determine if a point is inside a polygon.
    """
    x, y = point
    inside = False

    for i in range(len(polygon)):
        x1, y1 = polygon[i]["start"]
        x2, y2 = polygon[i]["end"]

        # Check if the point is within the y-range of the edge
        if (y1 > y) != (y2 > y):
            # Compute the x-coordinate of the intersection of the edge with the ray
            x_intersect = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < x_intersect:
                inside = not inside

    return inside

def is_polygon_in_polygon(inner_polygon, outer_polygon):
    """
    Check if all points of `inner_polygon` are inside `outer_polygon`.
    """
    for segment in inner_polygon:
        if not is_point_in_polygon(segment["start"], outer_polygon):
            return False
        if not is_point_in_polygon(segment["end"], outer_polygon):
            return False
    return True

def extract_numeric_layer_name(layer_name):
    """
    Extract all digits from the layer name and return them as a single integer.
    If no digits are found, return 0.
    """
    digits = re.findall(r'\d+', layer_name)  # Find all numeric parts
    if digits:
        return int(''.join(digits))  # Combine and convert to an integer
    return 0

def unify_to_layers_in_place(input_dxf, output_dxf, tolerance=0.01):
    """
    Modify the existing DXF model to:
    1) Merge endpoints of lines and arcs.
    2) Group connected entities into layers.
    3) Join lines into polylines where possible.
    4) Assign circles to a separate layer.
    5) Save the modified DXF to a new file, preserving metadata.
    """
    doc_in = ezdxf.readfile(input_dxf)
    msp_in = doc_in.modelspace()

    # if the document version is not 2018, display a warning on the screen, asking the user to use the 2018 format if they want units to work properly
    if doc_in.dxfversion != "AC1032":
        print(f"Warning: The document version is not version 2018 (AC1032).")
        print(f"Please use the 2018 format if you want units to work properly in Affinity Designer (import as 'all pages').")

    # 1) Extract lines/arcs
    entities = extract_entities(msp_in)

    # 2) Merge endpoints
    entities = unify_endpoints(entities, tolerance=tolerance)

    # 3) Find connected groups (each group is a set of entity indices)
    groups = find_connected_groups(entities)

    # 4) Modify the existing modelspace
    polygons = []  # Store all polygons for containment checks
    for i, group in enumerate(groups):
        # Build a list of entity dicts for that group
        group_ents = [entities[idx] for idx in group]

        # Separate lines vs arcs
        lines = [e for e in group_ents if e["type"] == "LINE"]
        arcs = [e for e in group_ents if e["type"] == "ARC"]

        # Create a unique layer for this group
        layer_name = f"Part {i+1}"
        if arcs:
            layer_name = f"{layer_name} - Join Manually!"
        if not doc_in.layers.has_entry(layer_name):
            doc_in.layers.new(name=layer_name)

        polygon = []
        # 5) Add joined polylines for lines and remove original lines
        line_polylines = chain_lines(lines)  # each is a list of (x, y)
        for poly_pts in line_polylines:
            if len(poly_pts) < 2:
                continue
            new_polyline = msp_in.add_lwpolyline(
                points=poly_pts,
                format="xy",
                dxfattribs={"layer": layer_name}
            )
            # Store the handle of the new polyline
            for i in range(len(poly_pts) - 1):
                # Store the start and end points of the polyline
                polygon.append({"start": poly_pts[i], "end": poly_pts[i+1], "handle": new_polyline.dxf.handle})

        # Remove original lines from the modelspace
        for line in lines:
            handle = line["handle"]
            original_entity = doc_in.entitydb.get(handle)
            if original_entity:
                msp_in.delete_entity(original_entity)

        # 6) Update arcs to the new layer
        for arc in arcs:
            handle = arc["handle"]
            original_arc = doc_in.entitydb.get(handle)
            if original_arc:
                # Move the original arc to the new layer
                original_arc.dxf.layer = layer_name

        # Approximate arcs as line segments and store the polygon
        for ent in group_ents:
            if ent["type"] == "ARC":
                polygon.extend(approximate_arc(ent))
        polygons.append((polygon, layer_name))

    # 7) Check for polygon containment
    for i, (inner_polygon, inner_layer) in enumerate(polygons):
        for j, (outer_polygon, outer_layer) in enumerate(polygons):
            if i != j and is_polygon_in_polygon(inner_polygon, outer_polygon):
                # Update the layer name for the contained polygon
                new_layer_name = f"{outer_layer} - Contained"
                if not doc_in.layers.has_entry(new_layer_name):
                    doc_in.layers.new(name=new_layer_name)

                # Update the layer of all entities in the contained polygon
                for segment in inner_polygon:
                    handle = segment["handle"]
                    original_entity = doc_in.entitydb.get(handle)
                    if original_entity:
                        original_entity.dxf.layer = new_layer_name

    # 8) Assign circles to a separate layer or check if they are inside a closed polygon
    circle_layer_name = "Individual Circles"
    if not doc_in.layers.has_entry(circle_layer_name):
        doc_in.layers.new(name=circle_layer_name)

    for circle in msp_in.query("CIRCLE"):
        center = (circle.dxf.center.x, circle.dxf.center.y)
        radius = circle.dxf.radius

        # Check if the circle is inside any closed polygon
        inside_polygon = False
        for polygon, layer_name in polygons:
            if is_point_in_polygon(center, polygon):
                wrapping_handle = polygon[0]["handle"]  # Use the handle of the first segment as the layer name
                wrapping_entity = doc_in.entitydb.get(wrapping_handle)
                if wrapping_entity:
                    circle_layer_name = f"{wrapping_entity.dxf.layer} - Contained"
                # circle_layer_name = f"Part {i+1} - Inside Circles"
                break

        # Assign the circle to the appropriate layer
        circle.dxf.layer = circle_layer_name

    # 9) Sort entities by numeric layer name before saving
    # Extract all entities from the modelspace
    entities = msp_in.query("*")

    # Update the redraw order based on the sorted entities
    msp_in.set_redraw_order(
        (entity.dxf.handle, 10000 - extract_numeric_layer_name(entity.dxf.layer) ) 
        for entity in entities)


    # 10) Save the modified DXF to a new file
    doc_in.saveas(output_dxf)
    print(f"Done. Connected geometry grouped into layers in the existing model.")
    print(f"Wrote: {output_dxf}")
    

import sys

if __name__ == "__main__":
    import os

    # Dynamically get the tool name
    tool_name = os.path.basename(sys.argv[0])

    # Check if at least the input file is provided
    if len(sys.argv) < 2:
        print(f"Usage: python {tool_name} <input_file.dxf> [output_file.dxf] [tolerance]")
        sys.exit(1)

    # Parse input file
    input_file = sys.argv[1]

    # Parse output file or generate default output file name
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    else:
        base_name, ext = os.path.splitext(input_file)
        output_file = f"{base_name}-auto-bound{ext}"

    # Parse tolerance or use default
    if len(sys.argv) > 3:
        try:
            tolerance = float(sys.argv[3])
        except ValueError:
            print(f"Error: Tolerance must be a numeric value.\nUsage: python {tool_name} <input_file.dxf> [output_file.dxf] [tolerance]")
            sys.exit(1)
    else:
        tolerance = 0.01  # Default tolerance

    # Call the main function
    unify_to_layers_in_place(input_file, output_file, tolerance=tolerance)