# tte.js

Terminal-style text effects for the browser, written in plain JavaScript.

`tte.js` animates ASCII art and text on a Canvas. It has no dependencies and
does not load WebAssembly.

The library adapts all 37 effects from
[TerminalTextEffects](https://github.com/ChrisBuilds/terminaltexteffects) by
[ChrisBuilds](https://github.com/ChrisBuilds):

`beams`, `binarypath`, `blackhole`, `bouncyballs`, `bubbles`, `burn`,
`colorshift`, `crumble`, `decrypt`, `errorcorrect`, `expand`, `fireworks`,
`highlight`, `laseretch`, `matrix`, `middleout`, `orbittingvolley`, `overflow`,
`pour`, `print`, `rain`, `randomsequence`, `rings`, `scattered`, `slice`,
`slide`, `smoke`, `spotlights`, `spray`, `swarm`, `sweep`, `synthgrid`,
`thunderstorm`, `unstable`, `vhstape`, `waves`, and `wipe`.

## Use it

Download the
[tte.js ZIP](https://flaviocopes.com/software/tte-js/tte-js.zip) and extract it
inside your project.

Then add the text you want to animate:

```html
<pre id="title">WELCOME TO THE TERMINAL</pre>
```

Import the library from the extracted directory:

```js
import { createTextEffect } from './tte.js/src/index.js'

const animation = createTextEffect('#title', {
  effect: 'laseretch',
  duration: 2400,
  colors: ['#8a5cff', '#00d1ff', '#ffffff'],
})
```

The original `<pre>` controls the size, font, and layout. Canvas draws directly
over it. Screen readers still receive the original text.

## Control playback

The returned object controls the animation:

```js
await animation.play()

animation.stop()
animation.restart()

await animation.setEffect('decrypt')
```

Call `destroy()` when you no longer need it:

```js
animation.destroy()
```

This removes the Canvas and restores the original element styles.

## Use the custom element

Register the custom element once:

```js
import { defineTextEffectElement } from './tte.js/src/index.js'

defineTextEffectElement()
```

You can now animate text directly from HTML:

```html
<text-effect
  effect="laseretch"
  duration="2400"
  colors="#8a5cff,#00d1ff,#ffffff"
>
  WELCOME TO THE TERMINAL
</text-effect>
```

Set `loop` to repeat the animation. The element also provides `play()`,
`restart()`, and `stop()` methods.

## Options

- `effect` selects any effect from the 37-effect catalog
- `duration` sets the animation length in milliseconds
- `colors` sets the final text gradient
- `hotColors` sets the laser cooling colors
- `laserColors` sets the laser beam gradient
- `seed` makes each run repeatable
- `fps` limits rendering, with a default of 60
- `loop` repeats the effect
- `autoplay` starts playback after setup
- `respectReducedMotion` shows the final frame when reduced motion is enabled
- `background` fills the Canvas before drawing each frame

## Add an effect

Effects receive the parsed grid, options, and a seeded random function. They
return an object with a `render()` method:

```js
import { registerEffect } from './tte.js/src/index.js'

registerEffect('appear', ({ grid }) => ({
  render(progress) {
    return {
      cells: grid.visibleCells.map((cell) => ({
        ...cell,
        alpha: progress,
        color: '#ffffff',
      })),
      particles: [],
    }
  },
}))
```

You can now pass `effect: 'appear'` to `createTextEffect()`.

## Run the demo

Start a local server:

```bash
npm run demo
```

Then open `/demo/`. The gallery renders every effect and lets you change its
speed, palette, and random seed.

## Rebuild the GIF

The demo includes a 14-second GIF containing every effect. You can rebuild it
after changing an effect:

```bash
npm run gif
```

The capture script needs Chrome, FFmpeg, and Node.js 20 or newer. It writes the
finished file to `demo/tte-effects.gif`.

## Credits

The effect names, concepts, and animation designs come from
[TerminalTextEffects](https://github.com/ChrisBuilds/terminaltexteffects).
[ttfx](https://github.com/omacom/ttfx), the Rust parity port maintained by
37signals and omacom, provided another reference for their behavior.

The project started after
[DHH shared ttfx running on the Omarchy homepage](https://x.com/dhh/status/2093771424234099030).
[Christoffer Hallas](https://x.com/hicsfh) ported ttfx to WebAssembly for that
page.

tte.js does not include that WebAssembly build. It reimplements the effects
with a JavaScript engine designed for Canvas and browser layouts.

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for the complete
attribution.

## License

tte.js is distributed under the MIT License.

The top-level [LICENSE](LICENSE) preserves the copyright notices for tte.js and
its upstream sources. The original upstream MIT license texts are included in
[LICENSES](LICENSES).
