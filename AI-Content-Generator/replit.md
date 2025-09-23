# Menu to Social Media Post Generator

## Overview

This is a Flask web application that transforms restaurant menu text into engaging Instagram-style social media posts using OpenAI's GPT models. Users can input their restaurant menu content and generate multiple customized social media posts complete with captions and hashtags. The application features a clean, Instagram-inspired UI and provides an easy way for restaurant owners to create professional social media content from their existing menu information.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend Architecture
- **Template Engine**: Jinja2 templates with Flask for server-side rendering
- **UI Framework**: Bootstrap 5.1.3 for responsive design and components
- **Styling**: Custom CSS with Instagram-inspired color scheme and gradients
- **Icons**: Font Awesome 6.0.0 for consistent iconography
- **Layout Pattern**: Base template inheritance for consistent navigation and styling across pages

### Backend Architecture
- **Web Framework**: Flask with minimal routing structure
- **Route Design**: Simple POST/GET pattern with form handling and template rendering
- **Error Handling**: Flash message system for user feedback and input validation
- **Session Management**: Flask sessions with configurable secret key
- **Input Validation**: Server-side validation for menu text and post count limits (1-10 posts)

### AI Integration
- **API Client**: OpenAI Python SDK for GPT model integration
- **Model Configuration**: Configurable model selection via environment variables (defaults to gpt-4o)
- **Prompt Engineering**: Single API call optimization for generating multiple posts simultaneously
- **Content Structure**: Structured output for captions and hashtags per post

### Configuration Management
- **Environment Variables**: API keys, model selection, and session secrets stored as environment variables
- **Fallback Values**: Default configurations for development environments
- **Validation**: Required environment variable validation on application startup

## External Dependencies

### AI Services
- **OpenAI API**: GPT models for content generation, requires OPENAI_API_KEY environment variable
- **Model Support**: Configurable model selection (default: gpt-4o)

### Frontend Libraries
- **Bootstrap 5.1.3**: CSS framework loaded via CDN for responsive UI components
- **Font Awesome 6.0.0**: Icon library loaded via CDN for consistent iconography

### Python Packages
- **Flask**: Web framework for application structure and routing
- **OpenAI**: Official Python SDK for OpenAI API integration

### Environment Configuration
- **OPENAI_API_KEY**: Required for AI content generation
- **OPENAI_MODEL**: Optional model selection (defaults to gpt-4o)
- **SESSION_SECRET**: Optional session key (defaults to development key)