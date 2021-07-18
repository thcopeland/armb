## ARMB

ARMB stands for Another Rendering Manager for Blender, which is pretty much what it is. ARMB is a Blender addon that allows you to render an animation across multiple computers over your network.

ARMB does something so stupidly simple, you could almost do it by hand. The ARMB supervisor allocates frames to the workers in a round-robin manner; the faster a computer is, the more frames it renders. Unlike more sophisticated distributed renderers, ARMB does not automatically sync files over your network. **You have to manually transfer every file necessary for a render to each computer.** ARMB does, however, synchronize image dimensions and percentage scale.

## Installation

Blender's Python API can change significantly between versions, so you'll want to choose the correct ARMB version for Blender installation. You should also use the same version of ARMB on all your computers.

| Blender Version     | ARMB Version
|---------------------|--------------------------
| 2.9*                | [0.1.0](https://github.com/thcopeland/armb/releases/tag/v0.1.0)

## Usage

After downloading the most appropriate version of ARMB, install it as a Blender addon on each computer you want to use. When you want to render an animation, begin by copying every file necessary for the render to each computer. Then navigate to the Render tab and find the ARMB Network Render panel.

![Initial Menu](https://github.com/thcopeland/armb/blob/master/doc/initial_menu.png)

#### Setting up a supervisor

On the computer you want to use as a supervisor, click `Start Supervisor`. Before you do that, though, you might want to change the output path. This is where all the rendered files will eventually end up. You'll then see this screen:

![Supervisor UI](https://github.com/thcopeland/armb/blob/master/doc/supervisor_menu.png)

The UI is largely self-explanatory, but some of the details are subtle.

 - The `Render` button starts rendering the animation.
 - The `Cancel` button stops a render. This just means that the supervisor stops assigning frames to workers and won't fetch rendered frames from them. Note that, unfortunately, the Blender Python API doesn't provide a way to reliably cancel an in-progress render. After clicking the `Cancel` button, however, you can press `ESC` on each worker to manually stop the render.
 - The `Add Worker` button attempts to connect to a worker.
 - The `Remove Worker` button removes a worker. If a render is in progress, the frames that were assigned to that worker will be reassigned and rerendered.
 - `Render display mode` indicates how rendering will affect the UI. `New Window`, for example, will render frames in a separate window, while `Image Editor` renders frames within the UI, inside the image editor view.
 - By default, ARMB also renders frames on the supervisor. You can change this by setting `Render on supervisor`, though I can't imagine why you'd want to.
 - `Disconnect` cancels the in-progress render, if any, and disconnects from the workers. If something goes wrong, you can use this to restart ARMB.

The workers are shown in a list. An icon indicates what the worker is currently doing: a solid dot means that the worker is ready, an empty dot means that it was unable to connect, circling arrows mean that the render settings are being synchronized, a camera means that the worker is rendering, and a "warning triangle" indicates that an error occurred.

#### Setting up a worker

On each computer you want to use as a worker, click `Start Worker`. You can change the output path if you feel like it, but the default should be fine. On the menu that pops up after you click `Start Worker`, you can set on which port the worker should run. The default (7210) should be fine, but if the worker fails to start, you should try something else.

![Worker UI](https://github.com/thcopeland/armb/blob/master/doc/worker_menu.png)

Workers are far simpler than supervisors. A helpful message indicates what's going on, and the `Disconnect` button allows you disconnect a worker from the supervisor. Any frames that were assigned to the worker will then be reassigned and rerendered.

If you cancel a render by pressing `ESC`, if the render was already canceled by the supervisor, the render will immediately stop and not recommence. If the supervisor did not cancel the render, however, the render will be retried twice, just in case you pressed it accidentally, before the worker gives up and starts on another frame. The original frame will be rendered by another worker.

## Is ARMB right for me?

ARMB has a few things going for it:

 - Lightweight. ARMB uses very little processing power, and, while rendering, very little memory (ARMB does use a lot of memory while uploading, but memory is less precious at that point, since rendering is complete).
 - Flexible. Some distributed renderers can only handle a single .blend file and have trouble with files that reference simulation data or external images. For ARMB, you copy every file you need to each computer: it's more work, but more flexible. ARMB also lets you do weird things, like render different files on each worker or use multiple workers on the same computer (one on the CPU and one on the GPU, for example).
 - Safe. It saves every file after rendering, so even if something crashes midway through a render, all the files are easily recoverable. ARMB also doesn't delete anything unless you tell it to.
 - In-flight changes. You can add and remove workers, and change the `Render on supervisor` behavior, during a render.

However, ARMB also has some significant drawbacks:

 - Animations only. Still images will be slightly slower over ARMB.
 - Should only be used over a local network. A single malicious worker or supervisor can crash the others.
 - Fragile. If a supervisor loses a connection, however briefly, the worker will be lost and have to be re-added.
 - Difficult to cancel renders. After pressing `Cancel` on the supervisor, you can either wait for every in-progress render to finish, or walk over to each computer and hit `ESC` to stop them. Other distributed renderers use multiple processes to avoid this.
 - Difficult to set up. ARMB requires you to copy the file you want to render manually to each computer. Many distributed renderers automatically synchronize the file in real time. This comes at the cost of making it much harder to handle external data, like simulations or some images.
 - Alpha. Currently, ARMB is in Alpha mode. Things should generally work, but you may run into strange issues. Please create an Issue on Github if this happens to you, so we can fix it.

For these reasons, you may want to use a more serious distributed rendering tool, like [Flamenco](https://www.flamenco.io/), [Pandora](https://prism-pipeline.com/pandora/), [Crowdrender](https://www.crowd-render.com/), or even something heavier, like [Sheepit](https://www.sheepit-renderfarm.com/).
