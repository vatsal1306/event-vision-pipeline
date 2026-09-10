import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatBytes(bytes: number, decimals = 1) {
  if (!+bytes) return '0 Bytes';
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
}

export function maskPhone(phone: string) {
  if (!phone || phone.length < 8) return phone;
  const isEmail = phone.includes('@');
  if (isEmail) {
    const [name, domain] = phone.split('@');
    return `${name.slice(0, 2)}***@${domain}`;
  }
  const last4 = phone.slice(-4);
  const prefix = phone.startsWith('+') ? phone.slice(0, 3) : '';
  return `${prefix} ******${last4}`;
}
