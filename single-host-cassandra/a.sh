a=5
for ((idc=1;idc<=$a;idc=$idc+1)); do let b=3+$idc*$a-$a; echo $b; done;
