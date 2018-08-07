#!/bin/bash

items=
for i in "$@"
do
	items="$items \"$i\""
done
for i in "$items"
do
	echo -e "$i\n"
done
