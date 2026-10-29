# Optional parking motivation extension

`normlab.parking-motivation@0.1.0` is a separate draft package. It imports the
generic `Motive` and `MotivationHypothesis`; it adds only a source-only parking
contribution bridge and scope-review command. The legacy parking package and
its generated artifacts are unchanged.

See [the consumer boundary and experiment protocol](../../../docs/PARKING_MOTIVATION.md).

`artifact-manifest.json` pins Ontology release 0.1.1, its source commit, all
upstream normalized IR bytes, local package input and generated output hashes.
The `upstream` directory contains exact copies from that release, under its
included MIT license. Version 0.1.0 of motivation-core remains draft vocabulary;
publishing a compiler release did not turn it into an executable graph profile.

Regenerate with a compiler built from the manifest's source commit:

```sh
ontologyc check ontology/parking-pilot/motivation/package.yaml
ontologyc compile ontology/parking-pilot/motivation/package.yaml \
  --target typescript --out ontology/parking-pilot/motivation/generated
npm run parking:motivation:check
```

Set build/cache/TMPDIR and LLVM_PROFILE_FILE to the verified external build
location before invoking a locally instrumented compiler. Generated SDK source
is committed in this package; transient build/profiling files are not.

The checker resolves imported relation endpoints against the pinned IRs, unlike
namespace-only compiler acceptance. Generated object schemas still do not
enforce graph policies. No eventcore profile, live route, legal rule or Lean
module is extended here.
