const fs = require('fs');
const axios = require('axios');

// Tambahkan teks ke README.md
const newText = 'Halo, ini adalah tambahan teks baru!';
const readmePath = 'README.md';

fs.readFile(readmePath, 'utf8', (err, data) => {
  if (err) {
    console.error(`Gagal membaca berkas ${readmePath}: ${err}`);
    process.exit(1);
  }

  const updatedText = data + '\n' + newText;

  fs.writeFile(readmePath, updatedText, 'utf8', (err) => {
    if (err) {
      console.error(`Gagal menulis ke berkas ${readmePath}: ${err}`);
      process.exit(1);
    }

    console.log(`Berkas ${readmePath} berhasil diperbarui.`);

    // Kirim notifikasi ke Telegram
    const chatId = '-1002039884441'; // Ganti dengan chat ID Anda
    const botToken = '6946505231:AAH2L1QKhNWEBfJSDwZImGRhkEwfBLQzyy8'; // Ganti dengan token bot baru Anda
    const message = `ℹ️ README.md diperbarui!\n\n${newText}`;

    axios.post(`https://api.telegram.org/bot${botToken}/sendMessage`, {
      chat_id: chatId,
      text: message,
      parse_mode: 'markdown',
    })
      .then(() => console.log('Notifikasi berhasil dikirim ke Telegram.'))
      .catch((error) => console.error(`Gagal mengirim notifikasi ke Telegram: ${error.message}`));
  });
});
