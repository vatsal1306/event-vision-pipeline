'use client';

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Calendar, X } from 'lucide-react';
import { EventType } from '@/types/event';
import { format } from 'date-fns';

const eventSchema = z.object({
  name: z.string().min(3, 'Event name must be at least 3 characters').max(200, 'Event name must be at most 200 characters'),
  dateStart: z.string().min(1, 'Start date is required'),
  dateEnd: z.string().optional(),
  eventType: z.enum(['wedding', 'corporate', 'birthday', 'other']),
  description: z.string().max(500, 'Description must be at most 500 characters').optional(),
});

export type EventFormData = z.infer<typeof eventSchema>;

interface EventFormProps {
  onSubmit: (data: EventFormData) => Promise<void>;
  onCancel: () => void;
  isLoading?: boolean;
  defaultValues?: Partial<EventFormData>;
}

export function EventForm({ onSubmit, onCancel, isLoading, defaultValues }: EventFormProps) {
  const [dateStart, setDateStart] = useState<Date | undefined>(defaultValues?.dateStart ? new Date(defaultValues.dateStart) : undefined);
  const [dateEnd, setDateEnd] = useState<Date | undefined>(defaultValues?.dateEnd ? new Date(defaultValues.dateEnd) : undefined);

  const form = useForm<EventFormData>({
    resolver: zodResolver(eventSchema),
    defaultValues: {
      name: defaultValues?.name || '',
      dateStart: defaultValues?.dateStart || '',
      dateEnd: defaultValues?.dateEnd || '',
      eventType: defaultValues?.eventType || 'wedding',
      description: defaultValues?.description || '',
    },
  });

  const handleSubmit = form.handleSubmit(async (data) => {
    await onSubmit(data);
  });

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div>
        <label htmlFor="name" className="block text-sm font-medium mb-1.5">
          Event Name
        </label>
        <Input
          id="name"
          placeholder="e.g., Rahul & Priya Wedding"
          {...form.register('name')}
          disabled={isLoading}
        />
        {form.formState.errors.name && (
          <p className="mt-1 text-sm text-destructive">{form.formState.errors.name.message}</p>
        )}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label htmlFor="dateStart" className="block text-sm font-medium mb-1.5">
            Start Date
          </label>
          <div className="relative">
            <Calendar className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              id="dateStart"
              type="date"
              value={dateStart ? format(dateStart, 'yyyy-MM-dd') : ''}
              onChange={(e) => {
                const newDate = e.target.value ? new Date(e.target.value) : undefined;
                setDateStart(newDate);
                form.setValue('dateStart', e.target.value);
              }}
              className="pl-10"
              disabled={isLoading}
            />
          </div>
          {form.formState.errors.dateStart && (
            <p className="mt-1 text-sm text-destructive">{form.formState.errors.dateStart.message}</p>
          )}
        </div>

        <div>
          <label htmlFor="dateEnd" className="block text-sm font-medium mb-1.5">
            End Date (optional)
          </label>
          <div className="relative">
            <Calendar className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              id="dateEnd"
              type="date"
              value={dateEnd ? format(dateEnd, 'yyyy-MM-dd') : ''}
              onChange={(e) => {
                const newDate = e.target.value ? new Date(e.target.value) : undefined;
                setDateEnd(newDate);
                form.setValue('dateEnd', e.target.value);
              }}
              className="pl-10"
              disabled={isLoading}
            />
          </div>
        </div>
      </div>

      <div>
        <label htmlFor="eventType" className="block text-sm font-medium mb-1.5">
          Event Type
        </label>
        <Select
          value={form.watch('eventType')}
          onValueChange={(value) => form.setValue('eventType', value as EventType)}
          disabled={isLoading}
        >
          <SelectTrigger id="eventType">
            <SelectValue placeholder="Select event type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="wedding">Wedding</SelectItem>
            <SelectItem value="corporate">Corporate</SelectItem>
            <SelectItem value="birthday">Birthday</SelectItem>
            <SelectItem value="other">Other</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div>
        <label htmlFor="description" className="block text-sm font-medium mb-1.5">
          Description (optional)
        </label>
        <Textarea
          id="description"
          placeholder="Add details about the event..."
          rows={3}
          {...form.register('description')}
          disabled={isLoading}
        />
        {form.formState.errors.description && (
          <p className="mt-1 text-sm text-destructive">{form.formState.errors.description.message}</p>
        )}
      </div>

      <div className="flex justify-end gap-3 pt-4">
        <Button type="button" variant="outline" onClick={onCancel} disabled={isLoading}>
          <X className="mr-2 h-4 w-4" />
          Cancel
        </Button>
        <Button type="submit" disabled={isLoading}>
          {isLoading ? 'Creating...' : 'Create Event'}
        </Button>
      </div>
    </form>
  );
}