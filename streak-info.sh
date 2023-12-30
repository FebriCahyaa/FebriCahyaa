#!/bin/bash

# Set zona waktu ke Asia/Jakarta
export TZ=Asia/Jakarta

# Ambil tanggal hari ini
today=$(date +"%Y-%m-%d")

# Baca tanggal terakhir berkontribusi dari berkas teks (ganti 'streak.txt' dengan nama berkas yang sesuai)
lastContribution=$(cat streak.txt)

# Bandingkan tanggal hari ini dengan tanggal terakhir berkontribusi
if [ "$today" == "$lastContribution" ]; then
  echo "Streak Anda masih berlanjut!"
else
  echo "Streak Anda terputus. Mulai lagi dari hari ini!"
fi
