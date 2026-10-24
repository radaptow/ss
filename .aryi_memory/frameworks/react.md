# Cheat-Sheet Técnico Maestro de React

## 1. Instalación y configuración inicial

### Windows
1. **Instalar Node.js**: Descarga e instala la última versión de Node.js desde [nodejs.org](https://nodejs.org/).
2. **Verificar instalación**: Abre el terminal y ejecuta `node -v` y `npm -v` para asegurarte de que se han instalado correctamente.
3. **Crear un nuevo proyecto**: Navega a tu directorio de trabajo y ejecuta `npx create-react-app my-app`.
4. **Iniciar el proyecto**: Navega al directorio del proyecto y ejecuta `npm start`.

### Linux
1. **Instalar Node.js**: Abre el terminal y ejecuta `sudo apt update` y `sudo apt install nodejs npm`.
2. **Verificar instalación**: Ejecuta `node -v` y `npm -v` para asegurarte de que se han instalado correctamente.
3. **Crear un nuevo proyecto**: Navega a tu directorio de trabajo y ejecuta `npx create-react-app my-app`.
4. **Iniciar el proyecto**: Navega al directorio del proyecto y ejecuta `npm start`.

## 2. Arquitectura y conceptos clave

### Componentes
- **Funcionales**: Son funciones JavaScript que devuelven JSX.
  ```jsx
  function Welcome(props) {
    return <h1>Hello, {props.name}</h1>;
  }
  ```
- **Clases**: Son clases JavaScript que extienden `React.Component`.
  ```jsx
  class Welcome extends React.Component {
    render() {
      return <h1>Hello, {this.props.name}</h1>;
    }
  }
  ```

### Estado y Props
- **Props**: Son propiedades inmutables que se pasan a los componentes.
- **Estado**: Es mutable y se usa para almacenar datos que pueden cambiar.

### Ciclo de Vida
- **Funcionales**: `useEffect`, `useContext`, `useReducer`, etc.
- **Clases**: `componentDidMount`, `componentDidUpdate`, `componentWillUnmount`, etc.

### Hooks
- **useState**: Permite agregar estado a componentes funcionales.
  ```jsx
  import React, { useState } from 'react';
  function Example() {
    const [count, setCount] = useState(0);
    return (
      <div>
        <p>You clicked {count} times</p>
        <button onClick={() => setCount(count + 1)}>
          Click me
        </button>
      </div>
    );
  }
  ```
- **useEffect**: Permite realizar efectos secundarios.
  ```jsx
  import React, { useEffect } from 'react';
  function Example() {
    useEffect(() => {
      document.title = `You clicked ${count} times`;
    });
    return (
      <div>
        <p>You clicked {count} times</p>
        <button onClick={() => setCount(count + 1)}>
          Click me
        </button>
      </div>
    );
  }
  ```

## 3. Patrones de código reales y funcionales listos para producción

### Renderizado condicional
```jsx
function Greeting(props) {
  const isLoggedIn = props.isLoggedIn;
  if (isLoggedIn) {
    return <h1>Welcome back!</h1>;
  }
  return <h1>Please sign up.</h1>;
}
```

### Listas y claves
```jsx
function NumberList(props) {
  const numbers = props.numbers;
  const listItems = numbers.map((number) =>
    <li key={number.toString()}>{number}</li>
  );
  return (
    <ul>{listItems}</ul>
  );
}
```

### Formularios
```jsx
class NameForm extends React.Component {
  constructor(props) {
    super(props);
    this.state = { value: '' };

    this.handleChange = this.handleChange.bind(this);
    this.handleSubmit = this.handleSubmit.bind(this);
  }

  handleChange(event) {
    this.setState({ value: event.target.value });
  }

  handleSubmit(event) {
    alert('A name was submitted: ' + this.state.value);
    event.preventDefault();
  }

  render() {
    return (
      <form onSubmit={this.handleSubmit}>
        <label>
          Name:
          <input type="text" value={this.state.value} onChange={this.handleChange} />
        </label>
        <input type="submit" value="Submit" />
      </form>
    );
  }
}
```

### Componentes controlados
```jsx
class NameForm extends React.Component {
  constructor(props) {
    super(props);
    this.state = { value: '' };

    this.handleChange = this.handleChange.bind(this);
    this.handleSubmit = this.handleSubmit.bind(this);
  }

  handleChange(event) {
    this.setState({ value: event.target.value });
  }

  handleSubmit(event) {
    alert('A name was submitted: ' + this.state.value);
    event.preventDefault();
  }

  render() {
    return (
      <form onSubmit={this.handleSubmit}>
        <label>
          Name:
          <input type="text" value={this.state.value} onChange={this.handleChange} />
        </label>
        <input type="submit" value="Submit" />
      </form>
    );
  }
}
```

## 4. Errores comunes a evitar

1. **Olvidar el uso de `key` en listas**: Cada elemento de una lista debe tener una `key` única.
2. **No usar variables globales**: Mantén el estado en el componente para evitar problemas de re-renderizado.
3. **No modificar el estado directamente**: Utiliza métodos como `setState` para actualizar el estado.
4. **No usar `this` en funciones flecha**: Asegúrate de usar métodos de clase para acceder a `this`.
5. **No olvidar el uso de `return` en funciones JSX**: Asegúrate de que las funciones JSX devuelvan JSX.

Este Cheat-Sheet te proporciona una visión general de cómo trabajar con React y cómo evitar errores comunes. ¡Buena suerte en tu viaje con React!
