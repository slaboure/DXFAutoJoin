When laser-cutting objects, a DXF file from a CAD tool (such as OnShape), must be used as a temporary representation in a design tool (à la Affinity Designer). Yet, a lot of information from the CAD software gets through that process, leading to a painful editing process. This tool simplifies that work by grouping in layers any lines, arcs, and circles that are likely supposed to work together as a unified path for the laser.

# The Problem
When exporting DXF files from CAD tools à la OnShape to prepare them for a laser cutting device, the DXF file consists of individual lines, arcs, and circles having no association. Yet, laser-cutting drivers typically require shapes to be bound for smooth cutting. This requires the operator to open the DXF file in a design tool (such as Affinity Designer 2), and carefully select lines and arcs that form one individual shape. That process is tedious and error-prone: different parts are typically very closely positioned, and they might contain inside elements (holes, gaps, etc.) that must NOT be joined with the external shape. 

# The Idea
The tool will find any line and arcs that are connected (or whose start/end points are sufficiently close) and put each closed shape in its own layer. Furthermore, when multiple lines are connected, it will transform them into polylines - thus further simplifying the process. 

However, the DXF format doesn't enable the assembly of lines and arcs together: when arcs are > 180°, they tend to "bulge" and the shape can change. As such, arcs are NOT merged with lines in the DXF file but simply added to the same layer as the lines they are connected to. To make such layers easy to identify, they are named "Part xxx - Join Manually!"

Lastly, a number of elements are embedded in other shapes, this includes circles for example (as drilling holes), but could be any shape. We are also using a relatively crude method to determine if any polygon is indeed embedded in another one, and, when that is the case, put them in a distinct layer with a similar name "Part xxx - Contained". This makes it easy to mass select/hide/unhide them when only printing a subset of your items.

# The process
When exporting your DXF, first make sure to use the 2018 format (not anything older). Then, call the DXF Auto Join tool (see below). This exports another DXF file, that you can then import in your design tool, and go to any "xxxx - Join Manually!" layer and manually join those shapes together.

Layers called "xxx - Contained", are used to group contained objects that shouldn't be bound together with the external shape, but that you might want to mass select to hide/unhide depending on what subset you want to print.

Note: when importing your DXF file in Affinity, make sure to select "all pages" or "Single Page", but not "Model" - otherwise your measurement/units won't work properly.

# Installation
Make sure you have python locally installed

Then, install the ezdxf library:
`pip install ezdxf`

Possibly make your file executable
`chmod +x DXFAutoJoin.py`

# Usage
`DXFAutoJoin.py <source DXF filename> [output DXF filename] [tolerance]`

- if the output filename is ignored, output will be set to source-processed.dxf (from source.dxf for example)
- if the tolerance is not set, it will be set to 0.01mm
