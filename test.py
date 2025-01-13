# Balances provided by the user
cw20_balances = [{'denom': 'factory/inj14ejqjyq8um4p3xfqj74yld5waqljf88f9eneuk/inj1c6lxety9hqn9q4khwqvjcfa24c2qeqvvfsg4fm', 'amount': 60000000.995426856}]
bank_balances = [{'denom': 'factory/inj14ejqjyq8um4p3xfqj74yld5waqljf88f9eneuk/inj1c6lxety9hqn9q4khwqvjcfa24c2qeqvvfsg4fm', 'amount': '1.0'}, 
                 {'denom': 'factory/inj178zy7myyxewek7ka7v9hru8ycpvfnen6xeps89/DRUGS', 'amount': '4424.734513'}]

# Combine both balances
all_balances = cw20_balances + bank_balances

# Sum the amounts for each unique denomination
total_balances = {}
for balance in all_balances:
    denom = balance['denom']
    amount = float(balance['amount'])
    total_balances[denom] = total_balances.get(denom, 0) + amount


print(total_balances)