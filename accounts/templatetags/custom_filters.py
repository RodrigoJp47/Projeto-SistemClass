from django import template

register = template.Library()

@register.filter
def Get_item(list, index):
    """
    Permite acessar um item de uma lista usando um índice.
    Exemplo de uso no template: {{ minha_lista|Get_item:0 }}
    """
    try:
        return list[index]
    except (IndexError, TypeError):
        return '' # Retorna vazio se o índice não existir ou o item não for uma lista