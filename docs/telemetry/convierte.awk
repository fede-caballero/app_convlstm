#!/usr/bin/gawk -f

BEGIN{


}


$1=="valid_time:"{
fecha=$2" "$3
}


$1=="callsign:"{
callsign=$2
}

$1=="lat:"{
lat=$2
}

$1=="lon:"{
lon=$2
}

$1=="alt:"{
alt=$2
}

$1=="gs:"{
gs=$2
}

$1=="gs:"{
if ( callsign == "VBCP")
  print  "\033[37m" callsign,fecha,"\n    ",lat,lon,"\n     Alt:",alt,"Gs:",gs,"\n\n";
else
if ( callsign == "VBCR")
  print  "\033[33m" callsign,fecha,"\n    ",lat,lon,"\n     Alt:",alt,"Gs:",gs,"\n\n";
else
if ( callsign == "VBCT")
  print  "\033[32m" "VBCU",fecha,"\n    ",lat,lon,"\n     Alt:",alt,"Gs:",gs,"\n\n";
else
if ( callsign == "VBCU")
  print  "\033[36m" "VBCT",fecha,"\n    ",lat,lon,"\n     Alt:",alt,"Gs:",gs,"\n\n";
else
if ( callsign == "VBBB")
  print  "\033[32m" callsign,fecha,"\n    ",lat,lon,"\n     Alt:",alt,"Gs:",gs,"\n\n";
  }
  
  

