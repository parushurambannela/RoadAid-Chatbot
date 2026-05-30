import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from '../services/auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './login.component.html',
  styleUrl: './login.component.css',
})
export class LoginComponent {
  email    = '';
  password = '';
  loading  = false;
  error    = '';

  constructor(private auth: AuthService, private router: Router) {}

  onSubmit(): void {
    if (!this.email || !this.password) return;

    this.loading = true;
    this.error   = '';

    this.auth.login(this.email, this.password).subscribe({
      next: () => this.router.navigate(['/chat']),
      error: (err) => {
        this.error   = err.error?.detail ?? 'Login failed. Please try again.';
        this.loading = false;
      },
    });
  }
}

