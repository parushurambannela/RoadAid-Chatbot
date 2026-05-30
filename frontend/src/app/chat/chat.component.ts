import { Component, ElementRef, ViewChild, AfterViewChecked } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AuthService } from '../services/auth.service';
import { ChatService } from '../services/chat.service';

export interface Message {
  role: 'user' | 'bot';
  text: string;
  loading?: boolean;
}

@Component({
  selector: 'app-chat',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './chat.component.html',
  styleUrl: './chat.component.css',
})
export class ChatComponent implements AfterViewChecked {
  @ViewChild('messageList') private messageList!: ElementRef<HTMLDivElement>;

  messages: Message[] = [
    {
      role: 'bot',
      text: `Hello, **${this.auth.getUserName()}**! 👋\nI'm the RoadAid AI assistant. Ask me anything about roads, accidents, drivers, or daily progress.`,
    },
  ];

  input     = '';
  sessionId: string | null = null;
  sending   = false;

  constructor(public auth: AuthService, private chat: ChatService) {}

  ngAfterViewChecked(): void {
    this.scrollToBottom();
  }

  private scrollToBottom(): void {
    try {
      const el = this.messageList.nativeElement;
      el.scrollTop = el.scrollHeight;
    } catch {}
  }

  send(): void {
    const question = this.input.trim();
    if (!question || this.sending) return;

    this.messages.push({ role: 'user', text: question });
    this.input   = '';
    this.sending = true;

    // Placeholder while waiting
    const placeholder: Message = { role: 'bot', text: '', loading: true };
    this.messages.push(placeholder);

    this.chat.sendMessage(question, this.sessionId).subscribe({
      next: (res) => {
        this.sessionId = res.session_id;
        placeholder.text    = res.answer;
        placeholder.loading = false;
        this.sending = false;
      },
      error: (err) => {
        placeholder.text    = err.status === 401
          ? 'Session expired. Please log in again.'
          : 'Something went wrong. Please try again.';
        placeholder.loading = false;
        this.sending = false;
        if (err.status === 401) this.auth.logout();
      },
    });
  }

  onKeyDown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.send();
    }
  }
}

