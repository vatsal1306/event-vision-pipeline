'use client';

import { useState } from 'react';
import { useGuests } from '@/hooks/use-analytics';
import { api } from '@/lib/api-client';
import { Button } from '@/components/ui/button';
import { Download, ChevronLeft, ChevronRight, ArrowUpDown } from 'lucide-react';
import { toast } from 'sonner';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

interface LeadTableProps {
  eventId: string;
}

export function LeadTable({ eventId }: LeadTableProps) {
  const [page, setPage] = useState(1);
  const [sortBy, setSortBy] = useState('guest_name');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
  const limit = 10;

  const { data, isLoading } = useGuests(eventId, page, limit, sortBy, sortOrder);

  const handleSort = (column: string) => {
    if (sortBy === column) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(column);
      setSortOrder('asc');
    }
    setPage(1);
  };

  const handleExport = async () => {
    try {
      // Fetch all for export (limit 1000 for mock)
      const res = await api.getAnalyticsGuests(eventId, 1, 1000, sortBy, sortOrder);
      const guestsList = res.guests;
      
      const headers = ['Name', 'Phone', 'First Visit', 'Photos Matched', 'Downloads'];
      const csvContent = [
        headers.join(','),
        ...guestsList.map((g: import('@/types/analytics').GuestAnalytics) => [
          `"${g.guest_name}"`,
          `"${g.guest_phone}"`,
          `"${g.first_visit ? new Date(g.first_visit).toLocaleDateString() : 'N/A'}"`,
          g.photos_matched_count,
          g.download_count
        ].join(','))
      ].join('\n');

      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.setAttribute('download', `event-${eventId}-guests.csv`);
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error) {
      toast.error('Export failed');
    }
  };

  const totalPages = data ? Math.ceil(data.total / limit) : 0;
  const guests = data?.guests || [];

  return (
    <div className="rounded-xl border bg-card text-card-foreground shadow-sm">
      <div className="p-6 flex flex-col md:flex-row items-center justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold">Guest Lead Capture</h3>
          <p className="text-sm text-muted-foreground">View and export guest details and engagement.</p>
        </div>
        <Button onClick={handleExport} variant="outline">
          <Download className="mr-2 h-4 w-4" /> Export CSV
        </Button>
      </div>
      
      <div className="relative w-full overflow-auto border-t">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="cursor-pointer" onClick={() => handleSort('guest_name')}>
                <div className="flex items-center">Name <ArrowUpDown className="ml-2 h-4 w-4" /></div>
              </TableHead>
              <TableHead>Phone</TableHead>
              <TableHead className="cursor-pointer" onClick={() => handleSort('first_visit')}>
                <div className="flex items-center">First Visit <ArrowUpDown className="ml-2 h-4 w-4" /></div>
              </TableHead>
              <TableHead className="cursor-pointer text-right" onClick={() => handleSort('photos_matched_count')}>
                <div className="flex items-center justify-end">Matches <ArrowUpDown className="ml-2 h-4 w-4" /></div>
              </TableHead>
              <TableHead className="cursor-pointer text-right" onClick={() => handleSort('download_count')}>
                <div className="flex items-center justify-end">Downloads <ArrowUpDown className="ml-2 h-4 w-4" /></div>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={5} className="h-24 text-center text-muted-foreground">
                  Loading guests...
                </TableCell>
              </TableRow>
            ) : guests.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="h-24 text-center text-muted-foreground">
                  No guests found.
                </TableCell>
              </TableRow>
            ) : (
              guests.map((guest: import('@/types/analytics').GuestAnalytics) => (
                <TableRow key={guest.guest_id}>
                  <TableCell className="font-medium">{guest.guest_name}</TableCell>
                  <TableCell>{guest.guest_phone}</TableCell>
                  <TableCell>{guest.first_visit ? new Date(guest.first_visit).toLocaleDateString() : 'N/A'}</TableCell>
                  <TableCell className="text-right">{guest.photos_matched_count}</TableCell>
                  <TableCell className="text-right">{guest.download_count}</TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {totalPages > 1 && (
        <div className="p-4 flex items-center justify-between border-t">
          <div className="text-sm text-muted-foreground">
            Page {page} of {totalPages}
          </div>
          <div className="space-x-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1 || isLoading}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage(p => Math.min(totalPages, p + 1))}
              disabled={page === totalPages || isLoading}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
