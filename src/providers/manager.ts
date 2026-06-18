import { LanguageProvider } from './provider';

export class ProviderManager {
    private providers: Map<string, LanguageProvider> = new Map();

    register(provider: LanguageProvider): void {
        this.providers.set(provider.languageId, provider);
    }

    getProvider(languageId: string): LanguageProvider | undefined {
        return this.providers.get(languageId);
    }

    async activateAll(): Promise<void> {
        for (const provider of this.providers.values()) {
            await provider.activate();
        }
    }

    async deactivateAll(): Promise<void> {
        for (const provider of this.providers.values()) {
            await provider.deactivate();
        }
    }

    getActiveProvider(languageId: string): LanguageProvider | undefined {
        const provider = this.providers.get(languageId);
        if (provider && provider.isReady()) {
            return provider;
        }
        return provider;
    }
}
