#!/bin/bash

MAXCAP=$2
whf=1
let hms=$whf+$MAXCAP
let hy=$hms+$MAXCAP
let zyq=$hy+$MAXCAP
let jx=$zyq+$MAXCAP
let zrq=$jx+$MAXCAP
let zx=$zrq+$MAXCAP
let oylz=$zx +$MAXCAP

user_no()
{
    case $1 in
        "whf")
            start_seq=$whf;;
        "hms")
            start_seq=$hms;;
        "hy")
            start_seq=$hy;;
        "zyq")
            start_seq=$zyq;;
        "zrq")
            start_seq=$zrq;;
        "jx")
            start_seq=$jx;;
        "zx")
            start_seq=$zx;;
	"oylz")
	    start_seq=$oylz;;
        *)
            start_seq="illegal"
    esac
    echo "$start_seq"
}

user_no $1
