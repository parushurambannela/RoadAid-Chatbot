import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface ChatResponse {
  answer: string;
  query: Record<string, unknown>;
  data: unknown[];
  session_id: string;
  error?: string;
}

@Injectable({ providedIn: 'root' })
export class ChatService {
  private readonly API = 'http://localhost:8000/api/v1';

  constructor(private http: HttpClient) {}

  sendMessage(question: string, sessionId: string | null): Observable<ChatResponse> {
    return this.http.post<ChatResponse>(`${this.API}/chat`, {
      question,
      session_id: sessionId,
    });
  }
}

