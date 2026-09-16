import { Metadata } from 'next';

type Props = {
  params: { slug: string };
  children: React.ReactNode;
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = params;
  
  try {
    // Determine the base URL for absolute image paths
    const baseUrl = process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000';
    
    // Fetch event public info directly from the backend
    // Assuming backend is running on process.env.NEXT_PUBLIC_API_BASE_URL or localhost:8000
    const apiUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
    const res = await fetch(`${apiUrl}/api/v1/event/${slug}/info`, {
      next: { revalidate: 60 }, // cache for 60 seconds
    });
    
    if (!res.ok) {
      return {
        title: 'Event Gallery',
      };
    }
    
    const data = await res.json();
    const eventName = data.event.name;
    const studioName = data.photographer.studio_name;
    const imageUrl = data.event.cover_image_url || data.photographer.logo_url;
    
    return {
      title: `${eventName} | by ${studioName}`,
      description: `View photos from ${eventName} captured by ${studioName}.`,
      openGraph: {
        title: `${eventName} | by ${studioName}`,
        description: `View photos from ${eventName} captured by ${studioName}.`,
        siteName: studioName,
        images: imageUrl ? [
          {
            url: imageUrl.startsWith('http') ? imageUrl : `${baseUrl}${imageUrl}`,
            width: 1200,
            height: 630,
            alt: eventName,
          }
        ] : [],
      },
      twitter: {
        card: 'summary_large_image',
        title: `${eventName} | by ${studioName}`,
        description: `View photos from ${eventName} captured by ${studioName}.`,
        images: imageUrl ? [imageUrl.startsWith('http') ? imageUrl : `${baseUrl}${imageUrl}`] : [],
      }
    };
  } catch (error) {
    return {
      title: 'Event Gallery',
    };
  }
}

export default function EventSlugLayout({ children }: Props) {
  return <>{children}</>;
}
