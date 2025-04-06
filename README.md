This tool processes DXF files output by CAD tools (such as OnShape) so that Design tools (such as Affinity Designer 2) have drawings pre-assembled - as much as it can.

# The Problem
When exporting DXF files from CAD tools à la OnShape to prepare them for a laser cutting device, the DXF file consists of individual lines, arcs, and circles having no association. Yet, laser-cutting drivers typically require shapes to be bound for smooth cutting. This requires the operator to open the DXF file in a design tool (such as Affinity Designer 2), and carefully select lines and arcs that form one individual shape. That process is tedious and error-prone: different parts are typically very closely positioned, and they might contain inside elements (holes, gaps, etc.) that must NOT be joined with the external shape. 

# The Idea
The tool will find any line and arcs that are connected (or whose start/end points are sufficiently close), and will put each closed shape in its own layer. Furthermore, when multiple lines are connected, it will transform them into polylines - thus further simplifying the process. 

However, the DXF format doesn't enable the assembly of lines and arcs together: when arcs are > 180°, they tend to "bulge" and the shape can change. As such, arcs are NOT merged with lines in the DXF file, but simply added to the same layer as the lines they are connected to. To make such layers easy to identify, they are named "Part xxx - Join Manually!"

Lastly, circles are typically not connected to parts (but rather holes in parts). They are all moved to an "Individual Circles" layer Further optimization might be required there.

# The process
When exporting your DXF, first make sure to use the 2018 format (not anything older). Then, call the DXF Auto Join tool (see below). This exports another DXF file, that you can then import in your design tool, and:
- go to any "Part xxx - Join Manually!" layer and manually join those shapes together
- visit the "Individual Circles" layer and see if you want to move them to their proper layers so that you do not mistakenly cut holes in a sheet when you want to simply hide a part

# Installation
Make sure you have python locally installed

Then, install the ezdxf library:
`pip install ezdxf`

Possibly make your file executable
`chmod +x DXFAutoJoin.py`

# Usage
`DXFAutoJoin.py <source DXF filename> [output DXF filename] [tolerance]`

- if the output filename is ignored, output will be set to source-auto-bound.dxf (from source.dxf for example)
- if the tolerance is not set, it will be set to 0.01mm
