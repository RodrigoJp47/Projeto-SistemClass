import requests
from django.core.management.base import BaseCommand
from accounts.models import Estado, Cidade

class Command(BaseCommand):
    help = 'Popula o banco de dados com estados e cidades do Brasil via API do IBGE'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('Iniciando a população de estados e cidades...'))

        # URL da API de estados do IBGE
        estados_url = 'https://servicodados.ibge.gov.br/api/v1/localidades/estados'
        response_estados = requests.get(estados_url)

        if response_estados.status_code != 200:
            self.stdout.write(self.style.ERROR('Falha ao buscar os estados.'))
            return

        estados = response_estados.json()
        estados_criados = 0
        cidades_criadas = 0

        for estado_data in sorted(estados, key=lambda e: e['sigla']):
            estado, created = Estado.objects.get_or_create(
                uf=estado_data['sigla'],
                defaults={'nome': estado_data['nome']}
            )
            if created:
                estados_criados += 1
                self.stdout.write(f"Estado '{estado.uf}' criado.")

            # URL da API de municípios para o estado atual
            cidades_url = f'https://servicodados.ibge.gov.br/api/v1/localidades/estados/{estado.uf}/municipios'
            response_cidades = requests.get(cidades_url)

            if response_cidades.status_code == 200:
                cidades = response_cidades.json()
                for cidade_data in cidades:
                    cidade, created = Cidade.objects.get_or_create(
                        nome=cidade_data['nome'],
                        estado=estado
                    )
                    if created:
                        cidades_criadas += 1
            else:
                self.stdout.write(self.style.WARNING(f"Falha ao buscar cidades para {estado.uf}."))

        self.stdout.write(self.style.SUCCESS(
            f'Processo finalizado! {estados_criados} estados e {cidades_criadas} cidades foram adicionados.'
        ))