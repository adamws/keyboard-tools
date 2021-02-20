# Features

## Matrix position assignment

By default, KiCad project generator attempts to automatically assign
row and column to a key. This assignment is based on absolute position
of a key.

User can also provide layout with annotated keys. In order to use annotations,
`Matrix->Predefined` must be selected.

Annotations must be defined as **top left** legend and follow this
format: `row,column`, for example:

``` json
["0,0", "0,1"],
["1,0", "1,1"]
```

Which produces this layout:

![2x2](./assets/2x2.png)

## Footprint library

User can choose between two footprint libraries: [perigoso/keyswitch-kicad-library](https://github.com/perigoso/keyswitch-kicad-library)
and [ai03-2725/MX_Alps_Hybrid](https://github.com/ai03-2725/MX_Alps_Hybrid).
MX_Alps_Hybrid has become de facto standard in mechanical keyboard maker
community but alternative by perigoso (which is based on ai03-2725 work)
is being merged to official KiCad footprint library.

There are some slight differences between the two. For example, stabilizer
mounting holes in perigoso library are not part of switch footprint.
Also, available key widths are not the same for both.

Nevertheless, this option is mainly personal preference and both choices should
produce valid PCB.

::: tip
If there is no footprint available for key in provided layout file, then
footprint for 1U key will be used instead.
:::

## Switch footprint

Three footprint types are supported: Cherry MX, Alps and Cherry MX/Alps hybrid.

## Routing

KiCad project generator implements simple track routing. It attempts to connect
switch matrix columns and rows. By default, this option is disabled but user
can turn it on.

::: warning
Router does not implement any checks. It is possible that routed tracks violate
PCB manufacturer design rules or are entirely wrong. Most common problem is
collision with stabilizer mounting holes and routing for rotated switches.

Remember to always run KiCad DRC checks.
:::
