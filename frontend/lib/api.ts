export interface ApiStatus {
  status: string;
  files_in_buffer?: number;
  files_needed_for_run?: number;
  last_update?: string;
}

// Interface for a detected storm cell
export interface StormCell {
  lat: number;
  lon: number;
  max_dbz: number;
  type: string;
}

// Nueva interfaz para una imagen con sus coordenadas
export async function updateLocation(lat: number, lon: number, token: string) {
  const response = await fetch(`${API_BASE_URL}/api/user/location`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify({ latitude: lat, longitude: lon }),
  });

  if (!response.ok) {
    throw new Error('Failed to update location');
  }
}

export interface ImageWithBounds {
  url: string;
  bounds: [[number, number], [number, number]];
  target_time?: string;
  timestamp_iso?: string;
  cells?: StormCell[];
}

// Actualizamos la interfaz principal de imágenes
export interface ApiImages {
  input_images: ImageWithBounds[];
  prediction_images: ImageWithBounds[];
}

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

// MOCK DATA FOR LOCAL TESTING
// We will load this from metadata.json if the API fails
let MOCK_DATA_CACHE: ImageWithBounds[] | null = null;

async function getMockData(): Promise<ImageWithBounds[]> {
  if (MOCK_DATA_CACHE) return MOCK_DATA_CACHE;
  try {
    const res = await fetch('/mock_data/metadata.json');
    if (res.ok) {
      MOCK_DATA_CACHE = await res.json();
      return MOCK_DATA_CACHE || [];
    }
  } catch (e) {
    console.error("Failed to load mock metadata", e);
  }
  return [];
}

const MOCK_STATUS: ApiStatus = {
  status: "OFFLINE",
  files_in_buffer: 0,
  files_needed_for_run: 8,
  last_update: undefined
};

async function fetchApi<T>(endpoint: string): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  try {
    const response = await fetch(url, { cache: 'no-store' });
    if (!response.ok) {
      throw new Error(`API request failed with status ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    console.warn(`Failed to fetch from ${url}, falling back to mock data.`);

    if (endpoint === '/api/status') return MOCK_STATUS as unknown as T;

    if (endpoint === '/api/images') {
      const images = await getMockData();
      // Split images for demo: first 10 as input, last 5 as prediction
      const splitIndex = Math.max(0, images.length - 5);
      const bufferSize = MOCK_STATUS?.files_in_buffer ?? 0
      const bufferMaxSize = MOCK_STATUS?.files_needed_for_run ?? 8
      const lastPredictionTime = MOCK_STATUS?.last_update
        ? new Date(MOCK_STATUS.last_update).toLocaleTimeString()
        : "--:--"
      return {
        input_images: images.slice(0, splitIndex),
        prediction_images: images.slice(splitIndex)
      } as unknown as T;
    }
    throw error;
  }
}

export const fetchStatus = (): Promise<ApiStatus> => fetchApi<ApiStatus>('/api/status');

// La función fetchImages ahora maneja la nueva estructura
export const fetchImages = async (): Promise<ApiImages> => {
  const data = await fetchApi<ApiImages>('/api/images');

  // Si estamos en modo mock (data ya tiene URLs relativas válidas), retornamos directo
  if ((data as any).input_images?.[0]?.url.startsWith('/')) {
    return data;
  }

  // Mapeamos sobre los arrays para construir las URLs absolutas si vienen del backend
  const processImages = (images: ImageWithBounds[]) => {
    if (!Array.isArray(images)) return [];
    return images.map(image => ({
      ...image,
      // Si la URL ya es absoluta o relativa, la dejamos. Si no, asumimos que es relativa a la raíz.
      url: image.url.startsWith('http') || image.url.startsWith('/') ? image.url : `/${image.url}`
    }));
  };

  return {
    input_images: processImages(data.input_images),
    prediction_images: processImages(data.prediction_images),
  };
};

// --- Reporting API ---

export interface WeatherReport {
  id?: number;
  report_type: string;
  latitude: number;
  longitude: number;
  timestamp?: string; // ISO
  description?: string;
  username?: string; // enriched by backend
  image?: File | null; // For upload
  image_url?: string; // From backend
}

export const submitReport = async (report: WeatherReport, token: string): Promise<void> => {
  let body: any;
  let headers: HeadersInit = {
    'Authorization': `Bearer ${token}`
  };

  if (report.image) {
    const formData = new FormData();
    formData.append('report_type', report.report_type);
    formData.append('latitude', report.latitude.toString());
    formData.append('longitude', report.longitude.toString());
    formData.append('description', report.description || '');
    formData.append('image', report.image);
    body = formData;
    // Content-Type header is not set manually for FormData, browser sets it with boundary
  } else {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(report);
  }

  const res = await fetch(`${API_BASE_URL}/api/reports`, {
    method: 'POST',
    headers: headers,
    body: body
  });
  if (!res.ok) throw new Error("Failed to submit report");
};

export const fetchReports = async (hours: number = 24): Promise<WeatherReport[]> => {
  try {
    const res = await fetch(`${API_BASE_URL}/api/reports?hours=${hours}`, { cache: 'no-store' }); // Ensure fresh data
    if (!res.ok) throw new Error("Failed to fetch reports");
    return await res.json();
  } catch (e) {
    console.error(e);
    return [];
  }
};

export const deleteReport = async (reportId: number, token: string): Promise<void> => {
  const res = await fetch(`${API_BASE_URL}/api/reports/${reportId}`, {
    method: 'DELETE',
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });

  if (!res.ok) {
    throw new Error("Failed to delete report");
  }
};

export const updateReport = async (reportId: number, data: { description?: string, image?: File }, token: string): Promise<void> => {
  const formData = new FormData();
  if (data.description !== undefined) formData.append('description', data.description);
  if (data.image) formData.append('image', data.image);

  const res = await fetch(`${API_BASE_URL}/api/reports/${reportId}`, {
    method: 'PUT',
    headers: {
      'Authorization': `Bearer ${token}`
    },
    body: formData
  });

  if (!res.ok) {
    throw new Error("Failed to update report");
  }
};

// --- Aircraft Telemetry ---

export interface Aircraft {
  icao24?: string;
  callsign: string;
  reg: string;
  lat: number;
  lon: number;
  heading: number;
  altitude: number;
  velocity: number;
  on_ground?: boolean;
  source?: string;  // 'opensky' | 'titan'
  trail?: [number, number][]; // History of [lon, lat] from backend
}

export const fetchAircraft = async (): Promise<Aircraft[]> => {
  try {
    const res = await fetch(`${API_BASE_URL}/api/aircraft`);
    if (!res.ok) return [];
    return await res.json();
  } catch (e) {
    console.error("Failed to fetch aircraft", e);
    return [];
  }
};

// --- Hail Swath ---

export const fetchHailSwathToday = async (): Promise<any> => {
  try {
    const res = await fetch(`${API_BASE_URL}/api/hail-swath/today`);
    if (!res.ok) return null;
    return await res.json();
  } catch (e) {
    console.error("Failed to fetch hail swath", e);
    return null;
  }
};

