# tiniest grammar (test fixture)

From [dantiston/delphin-tiniest-grammar](https://github.com/dantiston/delphin-tiniest-grammar),
a reduction of the 2020 Grammar Matrix's minimal grammar. It parses only `n1 iv`:

```
(subj-head (n1 "n1") (iv "iv"))
```

IGDE's tests use it to drive a real ACE: compiling, parsing, generating and
TFS browsing.  Two additions make generation work:

* `semi.vpm` (and `variable-property-mapping` in `config.tdl`, with
  `handle-type := handle.`) maps the grammar's variable types to the
  standard `e`/`x`/`h` sorts, so ACE can read the MRSs it prints back in;
* `skolem.tdl` supplies string types: ACE skolemizes each MRS variable as a
  string type during generation, and the original grammar has too few.
