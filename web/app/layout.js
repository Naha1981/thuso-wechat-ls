import './globals.css';
import OfflineStatus from './OfflineStatus';

export const metadata = {
  title: 'NahaOS',
  description: 'WhatsApp-first digital services and economic platform for Lesotho.',
  manifest: '/manifest.webmanifest',
};

export default function RootLayout({children}) {
  return <html lang="en"><body><OfflineStatus />{children}<script dangerouslySetInnerHTML={{__html: "if ('serviceWorker' in navigator) window.addEventListener('load',()=>navigator.serviceWorker.register('/sw.js'));"}} /></body></html>;
}
