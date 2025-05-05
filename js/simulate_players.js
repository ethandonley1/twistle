// js/simulate_players.js
import { faker } from 'https://cdn.skypack.dev/@faker-js/faker';
import { Filter } from 'https://cdn.skypack.dev/bad-words';

const filter = new Filter();

export function simulatePlayers(count = 100, fromDate = '2023-01-01', toDate = '2024-01-01') {
  const players = [];
  const start = new Date(fromDate);
  const end = new Date(toDate);

  for (let i = 0; i < count; i++) {
    const name = filter.clean(faker.name.findName());
    const score = faker.datatype.number({ min: 0, max: 10 });
    const date = new Date(start.getTime() + Math.random() * (end - start));
    players.push({ name, score, date: date.toISOString() });
  }
  return players;
}