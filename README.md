[Download v1.3.4 for Blender 4.0.2](https://github.com/artempoletsky/blender_half_knife/releases/download/v1.3.4/half_knife.zip)

This is a repository of Half Knife addon for Blender.

[User's guide](https://github.com/artempoletsky/half_knife_docs)

[Blender artists disussion](https://blenderartists.org/t/half-knife-fast-knife-tool-for-blender/)

## Guide for developers

1. Clone the repo.
2. Open `run.blend`
3. Turn off Half Knife in Blender's settings.
4. Modify the code.
5. Press `Run script` button on the `scripting` panel. See the result.

## Building and publishing

1. On Windows using 7zip 

    1.1 Right click on the `half_knife` folder.
    1.2 Choose `Add to 'half_knife.zip'`

2. Just pack the `half_knife` folder into a zip file. Just keep in mind that this zip file must contain a `half_knife` folder within.

## Project files overview

1. `./run.blend` - handy entry point for developing.
2. `./main.py` - script in the `run.blend` which loads `./half_knife/__init__.py`
3. `./code_snipets/` - contains example code snipets. They don't affect the addon in any way.
4. `./half_knife/__init__.py` - the main plugin entry point. Contains most of the plugin logic. 
5. `./half_knife/draw.py` - class `Draw` that is responsible of drawing UI helpers (lines and dots).
6. `./half_knife/geometry_math.py` - class `GeometryMath` contains utility methods of converting screen 2D coordinates to 3D and vice versa; and etc.
7. `./half_knife/preferences.py` - here you can modify the addon's preferences in the Blender settings menu.
8. `./half_knife/profiler.py` - measures the cut operation performace. To enable it in the dev mode change `use_profiler = True` in the `preferences.py`

## __init__.py methods overview

### def modal(self, context, event):

Contains all mouse event handlers.

### def run_cut(self):

All cutting logic happens here. 

### def invoke(self, context, event):

Runs `modal` if `auto_cut` option isn't used or `run_cut` otherwise.

